// SSE 事件处理器模块
// 将所有对 EventSource 的 addEventListener 逻辑集中在这里，导出 registerSSEHandlers(eventSource, ctx)
// ctx 包含需要访问的外部变量与回调：{ answerElement, toolExecutions, currentActionIdRef, currentIterationRef, conversationHelpers }
// conversationHelpers 可包含：renderNodeResult, renderExplanation, renderAnswer, createQuestionElement, sanitizeFilename, getMimeType, downloadFileFromContent, fetchJSON

import { downloadFileFromContent, sanitizeFilename, getMimeType, generateConversationId } from './utils.js';

// 配置 marked 渲染器，使所有链接在新标签页打开，并支持 Mermaid
if (typeof marked !== 'undefined') {
    const renderer = new marked.Renderer();
    const originalLinkRenderer = renderer.link.bind(renderer);
    const originalCodeRenderer = renderer.code.bind(renderer);

    renderer.link = function (href, title, text) {
        const html = originalLinkRenderer(href, title, text);
        return html.replace(/^<a /, '<a target="_blank" rel="noopener noreferrer" ');
    };

    // 自定义代码块渲染器以支持 Mermaid
    renderer.code = function (code, language) {
        if (language === 'mermaid') {
            // 为 Mermaid 代码块创建特殊标记
            return `<div class="mermaid-diagram" data-mermaid-code="${encodeURIComponent(code)}"></div>`;
        }
        return originalCodeRenderer(code, language);
    };

    marked.setOptions({
        renderer: renderer,
        breaks: true,
        gfm: true
    });
}

// 初始化 Mermaid（如果可用）
if (typeof mermaid !== 'undefined') {
    mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        fontFamily: 'Arial, sans-serif'
    });
}

// 辅助函数:渲染 Markdown 并处理数学表达式和 Mermaid 图表(仅用于最终结果)
function parseMarkdownWithMath(content) {
    if (!content) return '';

    // 先保护数学表达式，避免被 Markdown 解析器处理
    const mathBlocks = [];
    let protectedContent = content;

    // 保护 $$ ... $$ 块级数学表达式（使用唯一标记）
    protectedContent = protectedContent.replace(/\$\$([\s\S]+?)\$\$/g, (match, formula) => {
        const index = mathBlocks.length;
        mathBlocks.push({ type: 'block', formula: formula.trim(), index });
        return `<span class="math-placeholder" data-math-index="${index}" data-math-type="block"></span>`;
    });

    // 保护 $ ... $ 行内数学表达式
    protectedContent = protectedContent.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
        const index = mathBlocks.length;
        mathBlocks.push({ type: 'inline', formula: formula.trim(), index });
        return `<span class="math-placeholder" data-math-index="${index}" data-math-type="inline"></span>`;
    });

    // 使用 marked 解析 Markdown
    let html = '';
    try {
        html = marked.parse(protectedContent);
    } catch (e) {
        console.warn('Markdown 解析失败:', e);
        html = protectedContent;
    }

    // 创建临时元素
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;

    // 查找所有数学占位符并替换为 KaTeX 渲染结果
    if (typeof katex !== 'undefined' && mathBlocks.length > 0) {
        const placeholders = tempDiv.querySelectorAll('.math-placeholder');
        placeholders.forEach(placeholder => {
            const index = parseInt(placeholder.getAttribute('data-math-index'));
            const mathBlock = mathBlocks[index];

            if (mathBlock) {
                try {
                    const rendered = katex.renderToString(mathBlock.formula, {
                        displayMode: mathBlock.type === 'block',
                        throwOnError: false,
                        errorColor: '#cc0000',
                        strict: false,
                        trust: true
                    });

                    // 创建一个临时容器来存放渲染结果
                    const span = document.createElement('span');
                    span.innerHTML = rendered;

                    // 替换占位符
                    placeholder.parentNode.replaceChild(span.firstChild, placeholder);
                } catch (e) {
                    console.warn(`KaTeX 渲染失败 (${mathBlock.type}, index ${index}):`, e, mathBlock.formula);
                    // 如果渲染失败，显示原始公式
                    const original = mathBlock.type === 'block'
                        ? `$$${mathBlock.formula}$$`
                        : `$${mathBlock.formula}$`;
                    placeholder.textContent = original;
                }
            }
        });
    }

    // 处理 Mermaid 图表
    if (typeof mermaid !== 'undefined') {
        const mermaidDiagrams = tempDiv.querySelectorAll('.mermaid-diagram');
        mermaidDiagrams.forEach((diagram, index) => {
            try {
                const code = decodeURIComponent(diagram.getAttribute('data-mermaid-code'));
                const id = `mermaid-${Date.now()}-${index}`;

                // 创建一个容器用于 Mermaid 渲染
                const container = document.createElement('div');
                container.className = 'mermaid';
                container.textContent = code;

                // 替换占位符
                diagram.parentNode.replaceChild(container, diagram);

                // 异步渲染 Mermaid 图表
                setTimeout(() => {
                    try {
                        mermaid.run({
                            nodes: [container]
                        });
                    } catch (e) {
                        console.warn('Mermaid 渲染失败:', e);
                        container.innerHTML = `<pre><code class="language-mermaid">${code}</code></pre>`;
                    }
                }, 0);
            } catch (e) {
                console.warn('Mermaid 图表处理失败:', e);
            }
        });
    }

    return tempDiv.innerHTML;
}

export function registerSSEHandlers(eventSource, ctx = {}) {
    if (!eventSource) return;
    const {
        answerElement,
        toolExecutions = {},
        currentActionIdRef = { value: null },
        currentIterationRef = { value: 1 },
        renderNodeResult,
        renderExplanation,
        renderAnswer,
        createQuestionElement,
        streamTextContent, // 从 ctx 中获取流式文本输出函数（用于模拟打字机效果）
        Icons,
        updatePlaybook,
        fetchPlaybook, // 添加 fetchPlaybook 到 ctx
        currentModel, // 从 ctx 中获取 currentModel
        playbookStorage, // 从 ctx 中获取 playbookStorage
        scheduleConversationListUpdate // 从 ctx 中获取延迟更新会话列表函数
    } = ctx;

    // 标记 agent_complete 的流式渲染状态，避免 complete 事件过早重置 UI
    let isAgentCompleteStreaming = false;
    // 标记是否已经收到 complete 事件
    let pendingCompleteEvent = false;

    // 默认打字机延迟（毫秒），可通过 ctx.typingDelay 覆盖
    const defaultTypingDelay = (ctx && typeof ctx.typingDelay === 'number' ? ctx.typingDelay : 25);

    // agent_start - 渲染用户问题
    eventSource.addEventListener('agent_start', event => {
        try {
            const data = JSON.parse(event.data);
            const questionText = data.query || data.text || '';

            if (!questionText) {
                console.warn('agent_start 事件缺少问题文本');
                return;
            }

            // 查找当前的 answerElement 的父容器
            const qaContainer = answerElement ? answerElement.parentElement : null;
            if (!qaContainer) {
                console.warn('无法找到 qa-container');
                return;
            }

            // 检查是否已经存在问题元素，避免重复渲染
            if (qaContainer.querySelector('.question')) {
                console.log('问题已存在，跳过渲染');
                return;
            }

            // 创建问题元素（参考 sendMessage 中的渲染方式）
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question';

            // 添加复制按钮
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn small';
            copyBtn.innerHTML = `
                <svg class="copy-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z"></path>
                    <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z"></path>
                </svg>
                <span class="copy-tooltip">复制</span>
            `;
            questionDiv.appendChild(copyBtn);

            // 添加问题文本（使用 Markdown 渲染）
            const questionTextDiv = document.createElement('div');
            questionTextDiv.className = 'question-text';
            questionTextDiv.innerHTML = marked.parse(questionText);
            questionDiv.appendChild(questionTextDiv);

            // 将问题插入到 qa-container 的开头（在 answer 之前）
            qaContainer.insertBefore(questionDiv, answerElement);

            console.log('agent_start: 已渲染用户问题');
        } catch (error) {
            console.error('解析 agent_start 事件失败:', error);
        }
    });

    // agent_selection
    eventSource.addEventListener('agent_selection', event => {
        try {
            const data = JSON.parse(event.data);
            const selectionDiv = document.createElement('div');
            selectionDiv.className = 'agent-event agent-selection';
            selectionDiv.innerHTML = `
                <div class="agent-event-card">
                    <div class="agent-header">
                        <div class="agent-icon">🤖</div>
                        <div class="agent-meta">
                            <span class="agent-name">${data.agent_name}</span>
                        </div>
                    </div>
                    <div class="agent-content">
                        <div class="agent-section">
                            <div class="agent-detail">
                                <span class="detail-label">任务:</span>
                                <span class="detail-value">${data.agent_task}</span>
                            </div>
                            <div class="agent-detail">
                                <span class="detail-label">选择原因:</span>
                                <span class="detail-value">${data.selection_reason}</span>
                            </div>
                        </div>
                        <div class="agent-footer">
                            <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    </div>
                </div>
            `;
            if (answerElement) answerElement.appendChild(selectionDiv);
        } catch (error) {
            console.error('解析智能体选择事件失败:', error);
        }
    });

    // agent_execution
    eventSource.addEventListener('agent_execution', event => {
        try {
            const data = JSON.parse(event.data);
            const executionDiv = document.createElement('div');
            executionDiv.className = `agent-event agent-execution ${data.execution_step}`;

            let executionContent = '';
            if (data.execution_step === 'start') {
                executionContent = `
                    <div class="agent-event-card">
                        <div class="agent-header">
                            <div class="agent-icon">▶️</div>
                            <div class="agent-meta">
                                <span class="agent-name">${data.agent_name}</span>
                                <span class="agent-status">开始执行</span>
                            </div>
                        </div>
                        <div class="agent-content">
                            <div class="agent-section">
                                <div class="agent-detail">
                                    <span class="detail-label">可使用工具: </span>
                                    <span class="detail-value">${(data.execution_data && data.execution_data.tools || []).map(t => `<span class="tool-tag">${t}</span>`).join('')}</span>
                                </div>
                            </div>
                            <div class="agent-footer">
                                <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                            </div>
                        </div>
                    </div>`;
            } else if (data.execution_step === 'complete') {
                executionContent = `
                    <div class="agent-event-card">
                        <div class="agent-header">
                            <div class="agent-icon">✅</div>
                            <div class="agent-meta">
                                <span class="agent-name">${data.agent_name}</span>
                                <span class="agent-status">执行完成</span>
                            </div>
                        </div>
                        <div class="agent-content">
                            <div class="agent-section">
                                <div class="agent-detail">
                                    <span class="detail-label">执行结果:</span>
                                    <div class="detail-value result-content">${(data.execution_data && data.execution_data.result) ? (marked.parse(data.execution_data.result || '')) : ''}</div>
                                </div>
                                <div class="agent-detail">
                                    <span class="detail-label">状态:</span>
                                    <span class="detail-value">${(data.execution_data && data.execution_data.status) || ''}</span>
                                </div>
                            </div>
                            <div class="agent-footer">
                                <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                            </div>
                        </div>
                    </div>`;
            }

            executionDiv.innerHTML = executionContent;
            if (answerElement) answerElement.appendChild(executionDiv);
        } catch (error) {
            console.error('解析智能体执行事件失败:', error);
        }
    });

    // status
    eventSource.addEventListener('status', event => {
        const message = event.data;
        const statusDiv = document.createElement('div');
        statusDiv.className = 'status-message';
        statusDiv.textContent = message;
        if (answerElement) answerElement.appendChild(statusDiv);
    });

    // workflow
    eventSource.addEventListener('workflow', event => {
        currentIterationRef.value = (currentIterationRef.value || 1) + 1;
        try {
            const workflow = JSON.parse(event.data);
            const workflowDiv = document.createElement('div');
            workflowDiv.className = 'workflow-info collapsed';
            // 使用 Markdown 渲染工作流 JSON，便于美观显示并支持折叠样式
            const workflowMd = "```json\n" + JSON.stringify(workflow, null, 2) + "\n```";
            workflowDiv.innerHTML = `
                <div class="workflow-header">
                    <span>工作流已生成: ${(workflow.nodes && workflow.nodes.length) || 0} 个节点</span>
                </div>
                <div class="workflow-content">
                    ${marked.parse(workflowMd)}
                </div>
            `;
            if (answerElement) {
                answerElement.appendChild(workflowDiv);
                const workflowHeader = workflowDiv.querySelector('.workflow-header');
                if (workflowHeader) workflowHeader.onclick = () => workflowDiv.classList.toggle('collapsed');
            }
        } catch (error) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = '解析工作流失败';
            if (answerElement) answerElement.appendChild(errorDiv);
        }
    });

    // node_result
    eventSource.addEventListener('node_result', event => {
        try {
            const result = JSON.parse(event.data);
            // 如果当前节点完成，将之前所有运行中的节点标记为完成（UI 层处理）
            if (result.status === 'completed' && answerElement) {
                const runningNodes = answerElement.querySelectorAll('.node-result.running');
                runningNodes.forEach(node => {
                    node.classList.remove('running');
                    node.classList.add('success');
                    const statusSpan = node.querySelector('.node-header span:last-child');
                    if (statusSpan) statusSpan.textContent = '执行完成';
                    const loadingIndicator = node.querySelector('.running-indicator');
                    if (loadingIndicator) loadingIndicator.remove();
                });
            }
            if (typeof renderNodeResult === 'function') {
                renderNodeResult(result, answerElement);
            }
        } catch (error) {
            if (answerElement) answerElement.innerHTML += `<div class="error">解析节点结果失败</div>`;
        }
    });

    // explanation
    eventSource.addEventListener('explanation', event => {
        try {
            const response = JSON.parse(event.data);
            if (response.success && response.data) {
                if (typeof renderExplanation === 'function') {
                    renderExplanation(response.data, answerElement);
                }
            } else if (!response.success) {
                if (answerElement) answerElement.innerHTML += `<div class="error">${response.error || '解析解释说明失败'}</div>`;
            }
        } catch (error) {
            if (answerElement) answerElement.innerHTML += `<div class="error">解析解释说明失败</div>`;
        }
    });

    // answer
    eventSource.addEventListener('answer', event => {
        try {
            const response = JSON.parse(event.data);
            if (response.success && response.data) {
                if (typeof renderAnswer === 'function') {
                    // 检查是否是最终块，通过 response.is_final 字段判断
                    const isFinal = response.is_final === true;
                    renderAnswer(response.data, answerElement, isFinal);
                }
            } else if (!response.success) {
                if (answerElement) answerElement.innerHTML += `<div class="error">${response.error || '解析回答失败'}</div>`;
            }
        } catch (error) {
            if (answerElement) answerElement.innerHTML += `<div class="error">解析回答失败</div>`;
        }
    });

    // tool_progress
    eventSource.addEventListener('tool_progress', event => {
        try {
            const data = JSON.parse(event.data);
            const actionId = data.action_id || (currentActionIdRef && currentActionIdRef.value);
            if (actionId) currentActionIdRef.value = actionId;
            if (toolExecutions && toolExecutions[actionId]) {
                toolExecutions[actionId].progress = data.progress;
            }

            const actionGroup = document.querySelector(`.action-group[data-action-id="${actionId}"]`);

            if (actionGroup) {
                const statusEl = actionGroup.querySelector('.action-group-item-status.running');
                if (statusEl) statusEl.textContent = `执行中 (${data.progress || 0}%)`;
            }
        } catch (error) {
            console.error('解析工具进度失败:', error);
        }
    });

    // user_input_required
    eventSource.addEventListener('user_input_required', event => {
        try {
            const data = JSON.parse(event.data);
            const inputDiv = document.createElement('div');
            inputDiv.className = 'user-input-container';

            let inputHtml = `
                <div class="input-prompt">${marked.parse(data.prompt)}</div>
                <div class="input-form">
            `;
            switch (data.input_type) {
                case 'geolocation':
                    // 将 agent_id 放到隐藏 input 的 dataset 中，便于 submitUserInput 从 input 上读取到 agent_id
                    inputHtml += `
                        <div class="geolocation-input" style="display:none">
                            <input type="hidden" class="input-field" id="user-input-${data.node_id}" ${data.agent_id ? `data-agent-id="${data.agent_id}"` : ''}>
                            <div class="geolocation-status">正在获取位置信息...</div>
                        </div>
                    `;
                    setTimeout(() => {
                        // submitUserInput 在 main.js 中，触发它需要 main.js 将函数传入 ctx（可选）
                        if (typeof ctx.submitUserInput === 'function') ctx.submitUserInput(data.node_id, 'geolocation', data.prompt, data.agent_id);
                    }, 100);
                    break;
                case 'local_browser':
                    inputHtml += `
                        <div class="local-browser-input">
                            <input type="number" class="input-field" id="user-input-${data.node_id}" ${data.agent_id ? `data-agent-id="${data.agent_id}"` : ''}
                                placeholder="输入本地浏览器应用端口号"
                                min="1024"
                                max="65535"
                                ${data.validation && data.validation.required ? 'required' : ''}
                            />
                        </div>
                    `;
                    break;
                case 'password':
                    inputHtml += `
                        <input type="password" class="input-field" id="user-input-${data.node_id}" ${data.agent_id ? `data-agent-id="${data.agent_id}"` : ''}
                            value="${data.default_value || ''}"
                            ${data.validation && data.validation.required ? 'required' : ''}
                            ${data.validation && data.validation.pattern ? `pattern="${data.validation.pattern}"` : ''}
                            ${data.validation && data.validation.min_length ? `minlength="${data.validation.min_length}"` : ''}
                            ${data.validation && data.validation.max_length ? `maxlength="${data.validation.max_length}"` : ''}
                        />
                    `;
                    break;
                default:
                    inputHtml += `
                        <input type="text" class="input-field" id="user-input-${data.node_id}" ${data.agent_id ? `data-agent-id="${data.agent_id}"` : ''}
                            value="${data.default_value || ''}"
                            ${data.validation && data.validation.required ? 'required' : ''}
                            ${data.validation && data.validation.pattern ? `pattern="${data.validation.pattern}"` : ''}
                            ${data.validation && data.validation.min_length ? `minlength="${data.validation.min_length}"` : ''}
                            ${data.validation && data.validation.max_length ? `maxlength="${data.validation.max_length}"` : ''}
                        />
                    `;
            }

            // 将 agent_id 放到 submit 按钮的 dataset 中，便于前端提交时回传
            inputHtml += `
                    <button class="submit-input" data-node-id="${data.node_id}" data-input-type="${data.input_type}" data-prompt="${data.prompt}" ${data.agent_id ? `data-agent-id="${data.agent_id}"` : ''}>提交</button>
                </div>
            `;

            inputDiv.innerHTML = inputHtml;
            if (answerElement) answerElement.appendChild(inputDiv);

            const submitButton = inputDiv.querySelector('.submit-input');
            if (submitButton) {
                submitButton.addEventListener('click', () => {
                    if (typeof ctx.submitUserInput === 'function') {
                        const nodeId = submitButton.getAttribute('data-node-id');
                        const inputType = submitButton.getAttribute('data-input-type');
                        const prompt = submitButton.getAttribute('data-prompt');
                        // 优先从按钮 dataset 读取 agentId，fallback 使用事件 data.agent_id（如果存在）
                        const agentId = submitButton.dataset && submitButton.dataset.agentId ? submitButton.dataset.agentId : (data.agent_id || undefined);
                        ctx.submitUserInput(nodeId, inputType, prompt, agentId);
                    }
                });
            }

            const inputField = document.getElementById(`user-input-${data.node_id}`);
            if (inputField) inputField.focus();
        } catch (error) {
            console.error('解析用户输入请求失败:', error);
            if (answerElement) answerElement.innerHTML += `<div class="error">解析用户输入请求失败</div>`;
        }
    });

    // tool_retry
    eventSource.addEventListener('tool_retry', event => {
        try {
            const data = JSON.parse(event.data);
            const retryDiv = document.createElement('div');
            retryDiv.className = 'tool-retry';
            retryDiv.innerHTML = `
                <div class="retry-info">
                    <span>工具 ${data.tool} 重试中 (${data.attempt}/${data.max_retries})</span>
                    <span class="retry-error">${data.error}</span>
                </div>
            `;
            if (answerElement) answerElement.appendChild(retryDiv);
        } catch (error) {
            console.error('解析工具重试失败:', error);
        }
    });

    // serper_search
    eventSource.addEventListener('serper_search', event => {
        try {
            const data = JSON.parse(event.data);
            const searchDiv = document.createElement('div');
            searchDiv.className = 'serper-search-results';

            let resultsHtml = '';
            if (data.results && data.results.length > 0) {
                resultsHtml = data.results.map(item => `
                    <div class="search-result-item">
                        <a href="${item.link}" target="_blank" class="result-title">${item.title}</a>
                        <p class="result-snippet">${item.snippet}</p>
                        <p class="result-link">${item.link}</p>
                    </div>
                `).join('');
            } else {
                resultsHtml = '<p>没有找到搜索结果。</p>';
            }

            searchDiv.innerHTML = `
                <div class="search-header">
                    <span class="search-icon">🔍</span>
                    <span class="search-query">Serper 搜索: ${data.query}</span>
                    <span class="search-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
                <div class="search-content">
                    ${resultsHtml}
                </div>
            `;
            if (answerElement) answerElement.appendChild(searchDiv);
        } catch (error) {
            console.error('解析 Serper 搜索事件失败:', error);
        }
    });

    // action_start
    eventSource.addEventListener('action_start', event => {
        try {
            const data = JSON.parse(event.data);
            const actionId = data.action_id || Date.now().toString();
            if (currentActionIdRef) currentActionIdRef.value = actionId;

            // file_write 使用 utils 下载
            if (data.action === 'file_write') {
                try {
                    const input = data.input || {};
                    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                    const baseName = sanitizeFilename(input.filename || 'file');
                    const extension = (input.format || 'txt').toLowerCase();
                    const fileName = `${baseName}_${timestamp}.${extension}`;
                    const mime = getMimeType(extension);
                    downloadFileFromContent(input.content || '', fileName, mime);
                } catch (e) {
                    console.warn('file_write 处理失败', e);
                }
            }

            toolExecutions[actionId] = {
                action: data.action,
                input: data.input,
                status: 'running',
                startTime: (data.timestamp * 1000) || Date.now(),
                progress: null,
                result: null,
                endTime: null
            };

            // 格式化参数显示内容
            let formattedInput = '';
            if (data.action === 'python_execute' && data.input && data.input.code) {
                // 对于 python_execute 工具，如果有 code 参数，单独渲染代码
                formattedInput = '<div class="python-code-section">';
                formattedInput += '<div class="code-label">Python 代码:</div>';

                // 使用 highlight.js 直接高亮代码并添加行号
                let highlightedCode = data.input.code;
                if (typeof hljs !== 'undefined') {
                    try {
                        highlightedCode = hljs.highlight(data.input.code, { language: 'python' }).value;
                    } catch (e) {
                        console.warn('代码高亮失败，使用原始代码', e);
                    }
                }

                // 将代码按行分割并添加行号
                const codeLines = highlightedCode.split('\n');
                const numberedCode = codeLines.map((line, index) => {
                    const lineNumber = index + 1;
                    return `<span class="code-line"><span class="line-number">${lineNumber}</span>${line}</span>`;
                }).join('\n');

                formattedInput += `<pre><code class="hljs language-python code-with-line-numbers">${numberedCode}</code></pre>`;

                // 如果还有其他参数，也显示出来
                const otherParams = Object.keys(data.input).filter(key => key !== 'code');
                if (otherParams.length > 0) {
                    const otherParamsObj = {};
                    otherParams.forEach(key => {
                        otherParamsObj[key] = data.input[key];
                    });
                    formattedInput += '<div class="other-params-section">';
                    formattedInput += '<div class="code-label">其他参数:</div>';
                    formattedInput += '<pre><code class="hljs language-json">' + JSON.stringify(otherParamsObj, null, 2) + '</code></pre>';
                    formattedInput += '</div>';
                }
                formattedInput += '</div>';
            } else {
                // 其他工具使用普通 JSON 格式
                formattedInput = '<pre><code class="hljs language-json">' + JSON.stringify(data.input, null, 2) + '</code></pre>';
            }

            // 创建工具调用展示在聊天流中，默认折叠
            const actionGroup = document.createElement('div');
            actionGroup.className = 'action-group collapsed'; // 默认添加 collapsed 类
            actionGroup.setAttribute('data-action-id', actionId);
            actionGroup.innerHTML = `
                <div class="action-group-header">
                    <div class="action-group-title">
                        <span class="tool-icon">${Icons && Icons[data.action] ? Icons[data.action] : '🛠️'}</span>
                        ${data.action}
                    </div>
                    <div class="action-group-meta">
                        <span class="action-group-status running">执行中</span>
                    </div>
                </div>
                <div class="action-group-content">
                    <div class="action-group-item running">
                        <div class="action-group-item-header">
                            <span class="action-group-item-name">参数</span>
                        </div>
                        <div class="action-group-item-details">
                            ${formattedInput}
                        </div>
                        <div class="action-group-item-metrics">
                            <div class="action-group-item-metric">
                                <span class="action-group-item-metric-label">开始时间:</span>
                                <span class="action-group-item-metric-value">${new Date(toolExecutions[actionId].startTime).toLocaleTimeString()}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            if (answerElement) {
                answerElement.appendChild(actionGroup);
                // 为 header 添加点击事件，切换 collapsed 类
                const actionGroupHeader = actionGroup.querySelector('.action-group-header');
                if (actionGroupHeader) {
                    actionGroupHeader.addEventListener('click', () => {
                        actionGroup.classList.toggle('collapsed');
                    });
                }
            }

        } catch (error) {
            console.error('解析action开始事件失败:', error);
        }
    });

    // action_complete
    eventSource.addEventListener('action_complete', event => {
        try {
            const data = JSON.parse(event.data);
            const actionId = data.action_id || (currentActionIdRef && currentActionIdRef.value);
            if (!actionId) {
                console.error('缺少action_id，且没有当前action_id');
                return;
            }
            if (toolExecutions[actionId]) {
                toolExecutions[actionId].status = 'completed';
                toolExecutions[actionId].result = data.result;
                toolExecutions[actionId].endTime = (data.timestamp * 1000) || Date.now();
                toolExecutions[actionId].duration = toolExecutions[actionId].endTime - toolExecutions[actionId].startTime;
                if (currentActionIdRef) currentActionIdRef.value = actionId;
            }

            const actionGroup = document.querySelector(`.action-group[data-action-id="${actionId}"]`);

            if (actionGroup) {
                // 更新 header 中的状态
                const headerStatusEl = actionGroup.querySelector('.action-group-status');
                if (headerStatusEl) {
                    headerStatusEl.textContent = '完成';
                    headerStatusEl.classList.remove('running');
                    headerStatusEl.classList.add('success');
                }

                // 将最近的 .agent-thinking 中的 .thinking-indicator 从 running 变为 completed
                const lastThinkingIndicator = answerElement.querySelector('.agent-thinking:last-of-type .thinking-indicator.running');
                if (lastThinkingIndicator) {
                    lastThinkingIndicator.classList.remove('running');
                    lastThinkingIndicator.classList.add('completed');
                }

                const itemDetails = actionGroup.querySelector('.action-group-item.running');
                if (itemDetails) {
                    itemDetails.classList.remove('running');
                    itemDetails.classList.add('success');
                    const statusEl = itemDetails.querySelector('.action-group-item-status');
                    if (statusEl) {
                        statusEl.textContent = '完成';
                        statusEl.className = 'action-group-item-status success';
                    }
                    const metricsEl = itemDetails.querySelector('.action-group-item-metrics');
                    if (metricsEl) {
                        metricsEl.innerHTML += `
                            <div class="action-group-item-metric">
                                <span class="action-group-item-metric-label">结束时间:</span>
                                <span class="action-group-item-metric-value">${new Date(toolExecutions[actionId].endTime).toLocaleTimeString()}</span>
                            </div>
                            <div class="action-group-item-metric">
                                <span class="action-group-item-metric-label">执行耗时:</span>
                                <span class="action-group-item-metric-value">${(toolExecutions[actionId].duration).toFixed(2)}ms</span>
                            </div>
                        `;
                    }
                }

                // 添加结果部分
                const resultDiv = document.createElement('div');
                resultDiv.className = 'action-group-item success';
                let renderedResult = '';
                if (typeof data.result === 'string') {
                    renderedResult = marked.parse(data.result);
                } else {
                    renderedResult = marked.parse("```json\n" + JSON.stringify(data.result, null, 2) + "\n```");
                }
                resultDiv.innerHTML = `
                    <div class="action-group-item-header">
                        <span class="action-group-item-name">执行结果</span>
                        <div class="action-group-item-actions">
                            <button class="copy-btn small" data-copy-target=".action-group-item-details pre">
                                <svg class="copy-icon" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z"></path>
                                    <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z"></path>
                                </svg>
                                <span class="copy-tooltip">复制</span>
                            </button>
                            <button class="view-details-btn small">
                                <svg class="view-icon" fill="currentColor" viewBox="0 0 24 24" width="16" height="16">
                                    <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="action-group-item-details">
                        ${renderedResult}
                    </div>
                `;
                actionGroup.querySelector('.action-group-content').appendChild(resultDiv);

                // 为新的复制按钮添加事件监听器
                const copyButton = resultDiv.querySelector('.copy-btn');
                if (copyButton) {
                    copyButton.addEventListener('click', (e) => {
                        const targetSelector = copyButton.dataset.copyTarget;
                        const targetElement = resultDiv.querySelector(targetSelector);
                        if (targetElement) {
                            const textToCopy = targetElement.textContent || targetElement.innerText;
                            navigator.clipboard.writeText(textToCopy).then(() => {
                                const tooltip = copyButton.querySelector('.copy-tooltip');
                                if (tooltip) {
                                    tooltip.textContent = '已复制!';
                                    setTimeout(() => {
                                        tooltip.textContent = '复制';
                                    }, 2000);
                                }
                            }).catch(err => {
                                console.error('复制失败:', err);
                            });
                        }
                    });
                }

                // 为新的弹框展示按钮添加事件监听器
                const viewDetailsButton = resultDiv.querySelector('.view-details-btn');
                if (viewDetailsButton) {
                    viewDetailsButton.addEventListener('click', () => {
                        const modal = document.getElementById('toolResultModal');
                        const modalContent = modal.querySelector('.modal-result-content');
                        const closeBtn = modal.querySelector('.close-modal-btn');
                        const modalCopyBtn = modal.querySelector('.modal-actions .copy-btn');

                        // 渲染原始结果到弹框
                        modalContent.innerHTML = marked.parse(data.result);
                        modal.classList.add('visible');

                        // 弹框内的复制按钮逻辑
                        if (modalCopyBtn) {
                            modalCopyBtn.onclick = () => {
                                const originalResultText = data.result; // 复制原始结果
                                navigator.clipboard.writeText(originalResultText).then(() => {
                                    const tooltip = modalCopyBtn.querySelector('.copy-tooltip');
                                    if (tooltip) {
                                        tooltip.textContent = '已复制!';
                                        setTimeout(() => {
                                            tooltip.textContent = '复制原始结果';
                                        }, 2000);
                                    }
                                }).catch(err => {
                                    console.error('复制失败:', err);
                                });
                            };
                        }

                        // 关闭弹框逻辑
                        closeBtn.onclick = () => {
                            modal.classList.remove('visible');
                            modalContent.innerHTML = ''; // 清空内容
                        };

                        // 点击外部关闭弹框
                        window.onclick = (event) => {
                            if (event.target === modal) {
                                modal.classList.remove('visible');
                                modalContent.innerHTML = '';
                            }
                        };
                    });
                }
            }

        } catch (error) {
            console.error('解析action完成事件失败:', error);
        }
    });

    // agent_thinking
    eventSource.addEventListener('agent_thinking', event => {
        try {
            const data = JSON.parse(event.data);
            const thinkingDiv = document.createElement('div');
            thinkingDiv.className = 'agent-thinking';
            thinkingDiv.innerHTML = `
                <div class="thinking-info">
                    <span class="thinking-indicator running"></span>
                    <span class="thinking-content"></span> <!-- 内容将直接填充 -->
                    <span class="thinking-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
            `;
            if (answerElement) {
                answerElement.appendChild(thinkingDiv);
                const thinkingContentSpan = thinkingDiv.querySelector('.thinking-content');
                const thoughtContent = data.thought || '智能体正在思考...'; // 提供默认文本
                // 暂时禁用流式输出，直接设置文本内容
                if (thinkingContentSpan) {
                    thinkingContentSpan.textContent = thoughtContent;
                }
            }
        } catch (error) {
            console.error('解析agent思考事件失败:', error);
        }
    });

    // agent_error
    eventSource.addEventListener('agent_error', event => {
        try {
            const data = JSON.parse(event.data);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'agent-error';
            errorDiv.innerHTML = `
                <div class="error-info">
                    <span class="error-icon">⚠️</span>
                    <span class="error-message">${data.error}</span>
                    <span class="error-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
            `;
            if (answerElement) answerElement.appendChild(errorDiv);
        } catch (error) {
            console.error('解析agent错误事件失败:', error);
        }
    });

    // agent_evaluation
    eventSource.addEventListener('agent_evaluation', event => {
        try {
            const data = JSON.parse(event.data);
            const evaluationDiv = document.createElement('div');
            evaluationDiv.className = 'agent-event agent-evaluation';
            let satisfactionIcon = data.evaluation_result && data.evaluation_result.is_satisfied ? '✓' : '✗';
            let satisfactionClass = data.evaluation_result && data.evaluation_result.is_satisfied ? 'satisfied' : 'unsatisfied';
            evaluationDiv.innerHTML = `
                <div class="agent-event-card">
                    <div class="agent-header">
                        <div class="agent-icon">🔍</div>
                        <div class="agent-meta">
                            <span class="agent-name">${data.agent_name}</span>
                            <div class="agent-status ${satisfactionClass}">
                                <span class="status-icon">${satisfactionIcon}</span>
                                <span>${data.evaluation_result && data.evaluation_result.is_satisfied ? '满意' : '不满意'}</span>
                            </div>
                        </div>
                    </div>
                    <div class="agent-content">
                        <div class="agent-section">
                            <div class="agent-detail">
                                <span class="detail-label">评估结果:</span>
                                <span class="detail-value">${data.evaluation_result && data.evaluation_result.reason}</span>
                            </div>
                            ${data.evaluation_result && data.evaluation_result.need_handover ? `
                            <div class="agent-detail">
                                <span class="detail-label">交接建议:</span>
                                <span class="detail-value">${data.evaluation_result.handover_suggestions}</span>
                            </div>` : ''}
                            ${data.feedback ? `<div class="agent-detail"><span class="detail-label">反馈:</span><span class="detail-value">${data.feedback}</span></div>` : ''}
                        </div>
                        <div class="agent-footer">
                            <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    </div>
                </div>
            `;
            if (answerElement) answerElement.appendChild(evaluationDiv);
        } catch (error) {
            console.error('解析智能体评估事件失败:', error);
        }
    });

    // agent_complete
    eventSource.addEventListener('agent_complete', event => {
        try {
            const data = JSON.parse(event.data);
            const content = data.result;
            console.debug('[SSE] agent_complete received, length=', (content || '').length);

            const completeDiv = document.createElement('div');
            completeDiv.className = 'agent-complete-final';

            // 直接渲染 Markdown，无需流式或打字机效果
            let renderedHtml = '';
            try {
                renderedHtml = parseMarkdownWithMath(content || '智能体已完成任务。');
            } catch (e) {
                // 回退为纯文本
                renderedHtml = (content || '智能体已完成任务。');
            }

            completeDiv.innerHTML = `
                <div class="complete-info">
                    <div class="action_complete">${renderedHtml}</div>
                    <div class="complete-actions">
                        <button class="action-btn copy-result-btn" title="复制">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                        </button>
                        <button class="action-btn screenshot-btn" title="截图">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                                <circle cx="12" cy="13" r="4"></circle>
                            </svg>
                        </button>
                        <button class="action-btn pdf-download-btn" title="下载PDF">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                                <line x1="12" y1="18" x2="12" y2="12"></line>
                                <line x1="9" y1="15" x2="15" y2="15"></line>
                            </svg>
                        </button>
                        <button class="action-btn like-btn" title="点赞">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                            </svg>
                        </button>
                        <button class="action-btn dislike-btn" title="点踩">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
                            </svg>
                        </button>
                        <button class="action-btn regenerate-btn" title="重新生成">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="23 4 23 10 17 10"></polyline>
                                <polyline points="1 20 1 14 7 14"></polyline>
                                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            `;

            if (answerElement) {
                answerElement.appendChild(completeDiv);

                // 添加按钮事件监听器
                const copyBtn = completeDiv.querySelector('.copy-result-btn');
                const screenshotBtn = completeDiv.querySelector('.screenshot-btn');
                const likeBtn = completeDiv.querySelector('.like-btn');
                const dislikeBtn = completeDiv.querySelector('.dislike-btn');
                const regenerateBtn = completeDiv.querySelector('.regenerate-btn');

                // 复制功能
                if (copyBtn) {
                    copyBtn.addEventListener('click', () => {
                        const textToCopy = content || '智能体已完成任务。';
                        navigator.clipboard.writeText(textToCopy).then(() => {
                            copyBtn.classList.add('success');
                            setTimeout(() => copyBtn.classList.remove('success'), 2000);
                        }).catch(err => {
                            console.error('复制失败:', err);
                        });
                    });
                }

                // 截图功能（使用html2canvas库，如果可用）
                if (screenshotBtn) {
                    screenshotBtn.addEventListener('click', async () => {
                        try {
                            if (typeof html2canvas !== 'undefined') {
                                const targetElement = completeDiv.querySelector('.action_complete');

                                // A4纸宽度：210mm = 794px (at 96 DPI)
                                const A4_WIDTH = 794;
                                const PADDING = 48; // 左右各24px内边距
                                const CONTENT_WIDTH = A4_WIDTH - (PADDING * 2);

                                // 截图时设置为A4纸宽度，让内容有足够空间展示
                                const canvas = await html2canvas(targetElement, {
                                    backgroundColor: '#f8f9fa', // 设置背景色
                                    scale: 2, // 提高清晰度
                                    logging: false,
                                    width: A4_WIDTH,
                                    // 通过CSS设置A4宽度和内边距
                                    onclone: (clonedDoc) => {
                                        const clonedElement = clonedDoc.querySelector('.action_complete');
                                        if (clonedElement) {
                                            // 设置固定宽度为A4纸宽度
                                            clonedElement.style.width = `${A4_WIDTH}px`;
                                            clonedElement.style.maxWidth = `${A4_WIDTH}px`;
                                            clonedElement.style.minWidth = `${A4_WIDTH}px`;
                                            clonedElement.style.boxSizing = 'border-box';

                                            // 添加内边距和样式
                                            clonedElement.style.padding = `32px ${PADDING}px`;
                                            clonedElement.style.backgroundColor = '#ffffff';
                                            clonedElement.style.borderRadius = '0';

                                            // 确保内部内容不会溢出
                                            clonedElement.style.overflow = 'visible';
                                            clonedElement.style.wordWrap = 'break-word';
                                            clonedElement.style.wordBreak = 'break-word';

                                            // 设置字体和行高，确保可读性
                                            clonedElement.style.fontSize = '14px';
                                            clonedElement.style.lineHeight = '1.8';
                                            clonedElement.style.color = '#333';

                                            // 处理内部所有元素，确保不超出宽度
                                            const allElements = clonedElement.querySelectorAll('*');
                                            allElements.forEach(el => {
                                                el.style.maxWidth = '100%';
                                                el.style.wordWrap = 'break-word';
                                            });

                                            // 特别处理代码块
                                            const codeBlocks = clonedElement.querySelectorAll('pre, code');
                                            codeBlocks.forEach(block => {
                                                block.style.whiteSpace = 'pre-wrap';
                                                block.style.wordBreak = 'break-word';
                                                block.style.overflowWrap = 'break-word';
                                            });
                                        }
                                    }
                                });

                                canvas.toBlob(blob => {
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = `agent-result-${Date.now()}.png`;
                                    a.click();
                                    URL.revokeObjectURL(url);
                                });
                                screenshotBtn.classList.add('success');
                                setTimeout(() => screenshotBtn.classList.remove('success'), 2000);
                            } else {
                                alert('截图功能需要html2canvas库支持');
                            }
                        } catch (err) {
                            console.error('截图失败:', err);
                        }
                    });
                }

                // PDF下载功能
                const pdfDownloadBtn = completeDiv.querySelector('.pdf-download-btn');
                if (pdfDownloadBtn) {
                    pdfDownloadBtn.addEventListener('click', async () => {
                        try {
                            // 检查 jsPDF 是否可用
                            if (typeof window.jspdf === 'undefined') {
                                alert('PDF生成库未加载，请刷新页面重试');
                                return;
                            }

                            const { jsPDF } = window.jspdf;
                            const targetElement = completeDiv.querySelector('.action_complete');

                            // 使用 html2canvas 将内容转换为图片
                            if (typeof html2canvas !== 'undefined') {
                                // A4纸尺寸（单位：mm）
                                const A4_WIDTH = 210;
                                const A4_HEIGHT = 297;
                                const MARGIN = 15; // 页边距
                                const CONTENT_WIDTH = A4_WIDTH - (MARGIN * 2);

                                // 创建 PDF 文档
                                const pdf = new jsPDF({
                                    orientation: 'portrait',
                                    unit: 'mm',
                                    format: 'a4'
                                });

                                // 将内容转换为 canvas
                                const canvas = await html2canvas(targetElement, {
                                    backgroundColor: '#ffffff',
                                    scale: 2,
                                    logging: false,
                                    width: 794, // A4宽度的像素值 (at 96 DPI)
                                    onclone: (clonedDoc) => {
                                        const clonedElement = clonedDoc.querySelector('.action_complete');
                                        if (clonedElement) {
                                            clonedElement.style.width = '794px';
                                            clonedElement.style.maxWidth = '794px';
                                            clonedElement.style.padding = '32px 48px';
                                            clonedElement.style.backgroundColor = '#ffffff';
                                            clonedElement.style.fontSize = '14px';
                                            clonedElement.style.lineHeight = '1.8';
                                            clonedElement.style.color = '#333';
                                            clonedElement.style.wordWrap = 'break-word';

                                            // 处理代码块
                                            const codeBlocks = clonedElement.querySelectorAll('pre, code');
                                            codeBlocks.forEach(block => {
                                                block.style.whiteSpace = 'pre-wrap';
                                                block.style.wordBreak = 'break-word';
                                            });
                                        }
                                    }
                                });

                                // 计算图片在 PDF 中的尺寸
                                const imgWidth = CONTENT_WIDTH;
                                const imgHeight = (canvas.height * imgWidth) / canvas.width;

                                // 将 canvas 转换为图片数据
                                const imgData = canvas.toDataURL('image/png');

                                // 如果内容高度超过一页，需要分页
                                let heightLeft = imgHeight;
                                let position = MARGIN;

                                // 添加第一页
                                pdf.addImage(imgData, 'PNG', MARGIN, position, imgWidth, imgHeight);
                                heightLeft -= (A4_HEIGHT - MARGIN * 2);

                                // 如果需要多页
                                while (heightLeft > 0) {
                                    position = heightLeft - imgHeight + MARGIN;
                                    pdf.addPage();
                                    pdf.addImage(imgData, 'PNG', MARGIN, position, imgWidth, imgHeight);
                                    heightLeft -= (A4_HEIGHT - MARGIN * 2);
                                }

                                // 保存 PDF
                                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                                pdf.save(`agent-result-${timestamp}.pdf`);

                                pdfDownloadBtn.classList.add('success');
                                setTimeout(() => pdfDownloadBtn.classList.remove('success'), 2000);
                            } else {
                                alert('PDF生成需要html2canvas库支持');
                            }
                        } catch (err) {
                            console.error('PDF生成失败:', err);
                            alert('PDF生成失败，请查看控制台了解详情');
                        }
                    });
                }

                // 点赞功能
                if (likeBtn) {
                    likeBtn.addEventListener('click', () => {
                        likeBtn.classList.toggle('active');
                        if (dislikeBtn.classList.contains('active')) {
                            dislikeBtn.classList.remove('active');
                        }
                        // TODO: 发送反馈到后端
                        console.log('用户点赞');
                    });
                }

                // 点踩功能
                if (dislikeBtn) {
                    dislikeBtn.addEventListener('click', () => {
                        dislikeBtn.classList.toggle('active');
                        if (likeBtn.classList.contains('active')) {
                            likeBtn.classList.remove('active');
                        }
                        // TODO: 发送反馈到后端
                        console.log('用户点踩');
                    });
                }

                // 重新生成功能
                if (regenerateBtn) {
                    regenerateBtn.addEventListener('click', () => {
                        try {
                            // 获取当前问题元素（最近的一个问题）
                            const historyItems = document.querySelectorAll('.history-item');
                            if (historyItems.length === 0) {
                                console.warn('没有找到历史记录');
                                return;
                            }

                            // 获取最后一个历史项中的问题文本
                            const lastHistoryItem = historyItems[historyItems.length - 1];
                            const questionTextElement = lastHistoryItem.querySelector('.question-text');

                            if (!questionTextElement) {
                                console.warn('没有找到问题文本');
                                return;
                            }

                            // 提取纯文本内容（去除HTML标签）
                            const questionText = questionTextElement.textContent.trim();

                            if (!questionText) {
                                console.warn('问题文本为空');
                                return;
                            }

                            const selectedModul = document.getElementById('model-select').value;
                            // 重新生成 conversationId（如果 ctx 中提供了 conversationIdStorage 和 currentModel）
                            if (ctx.conversationIdStorage) {
                                const newConversationId = generateConversationId();
                                ctx.conversationIdStorage[selectedModul] = newConversationId;
                                console.log('已生成新的 conversationId:', newConversationId);
                            }

                            // 清空对话历史
                            const conversationHistory = document.getElementById('conversation-history');
                            if (conversationHistory) {
                                conversationHistory.innerHTML = '';
                            }

                            // 清空右侧 playbook
                            const playbookContent = document.getElementById('playbook-content');
                            if (playbookContent) {
                                playbookContent.innerHTML = '';
                            }

                            // 清空 playbookStorage 中当前模型的内容
                            if (playbookStorage && currentModel) {
                                playbookStorage[currentModel] = '';
                            }

                            // 将问题文本填入输入框
                            const userInput = document.getElementById('user-input');
                            if (userInput) {
                                userInput.value = questionText;
                                userInput.disabled = false;
                            }

                            // 触发发送按钮点击事件
                            const sendButton = document.getElementById('send-button');
                            if (sendButton) {
                                sendButton.disabled = false;
                                // 使用 setTimeout 确保 DOM 更新完成后再触发点击
                                setTimeout(() => {
                                    sendButton.click();
                                }, 100);
                            }

                            console.log('重新生成:', questionText);
                        } catch (err) {
                            console.error('重新生成失败:', err);
                            alert('重新生成失败，请查看控制台了解详情');
                        }
                    });
                }
            }

            // agent_complete 渲染结束后，调用延迟更新会话列表函数
            if (typeof scheduleConversationListUpdate === 'function') {
                try {
                    scheduleConversationListUpdate();
                    console.log('agent_complete 渲染完成，已启动延迟更新会话列表');
                } catch (err) {
                    console.warn('启动延迟更新会话列表失败:', err);
                }
            }
        } catch (error) {
            console.error('解析agent完成事件失败:', error);
        }
    });

    // agent_completed（兼容别名，与 agent_complete 同逻辑）
    eventSource.addEventListener('agent_completed', event => {
        try {
            const data = JSON.parse(event.data);
            const content = data.result;
            console.debug('[SSE] agent_completed received, length=', (content || '').length);

            const completeDiv = document.createElement('div');
            completeDiv.className = 'agent-complete-final';

            // 直接渲染 Markdown，无需流式或打字机效果
            let renderedHtml = '';
            try {
                renderedHtml = parseMarkdownWithMath(content || '智能体已完成任务。');
            } catch (e) {
                renderedHtml = (content || '智能体已完成任务。');
            }

            completeDiv.innerHTML = `
            <div class="complete-info">
                <div class="action_complete">${renderedHtml}</div>
            </div>
        `;

            if (answerElement) {
                answerElement.appendChild(completeDiv);
            }
        } catch (error) {
            console.error('解析agent完成事件失败:', error);
        }
    });


    // playbook_update
    eventSource.addEventListener('playbook_update', event => {
        try {
            const data = JSON.parse(event.data);
            const tasks = data.tasks || [];

            if (tasks.length > 0 && typeof updatePlaybook === 'function') {
                // 使用提取的任务列表渲染 playbook
                updatePlaybook(tasks);
                console.log('Playbook 已更新，任务数量:', tasks.length);

                // 保存 playbook 内容到 playbookStorage，以便在切换模型或第二次 chat 时能够恢复
                if (playbookStorage && currentModel) {
                    const playbookContent = document.getElementById('playbook-content');
                    if (playbookContent) {
                        playbookStorage[currentModel] = playbookContent.innerHTML;
                    }
                }
            }
        } catch (error) {
            console.error('解析 playbook 更新事件失败:', error);
        }
    });

    // complete
    eventSource.addEventListener('complete', event => {
        eventSource.close();
        // 在会话完成时，将所有 .agent-thinking 中的 .thinking-indicator 从 running 变为 completed
        document.querySelectorAll('.agent-thinking .thinking-indicator.running').forEach(indicator => {
            indicator.classList.remove('running');
            indicator.classList.add('completed');
        });

        // 标记已收到 complete 事件
        pendingCompleteEvent = true;

        // 统一延迟触发 onComplete，给 agent_complete 流式渲染留出时间设置标记
        // 若 150ms 后仍未开始流式，则立即收尾；若已开始，则在 agent_complete 的收尾回调中触发
        setTimeout(() => {
            if (!isAgentCompleteStreaming) {
                if (typeof ctx.onComplete === 'function') ctx.onComplete();
            }
        }, Math.max(defaultTypingDelay * 12, 300));
    });

    // onerror
    eventSource.onerror = () => {
        eventSource.close();
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = '连接错误';
        if (answerElement) answerElement.appendChild(errorDiv);
        if (typeof ctx.onError === 'function') ctx.onError();
    };

    return {
        dispose: () => {
            try { eventSource.close(); } catch (e) { /* noop */ }
        }
    };
}