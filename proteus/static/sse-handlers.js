// SSE 事件处理器模块
// 将所有对 EventSource 的 addEventListener 逻辑集中在这里，导出 registerSSEHandlers(eventSource, ctx)
// ctx 包含需要访问的外部变量与回调：{ answerElement, toolExecutions, currentActionIdRef, currentIterationRef, conversationHelpers }
// conversationHelpers 可包含：renderNodeResult, renderExplanation, renderAnswer, createQuestionElement, sanitizeFilename, getMimeType, downloadFileFromContent, fetchJSON

import { downloadFileFromContent, sanitizeFilename, getMimeType } from './utils.js';

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
        Icons
    } = ctx;

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
                            <pre>${JSON.stringify(data.input, null, 2)}</pre>
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
            const completeDiv = document.createElement('div');
            completeDiv.className = 'agent-complete-final';
            completeDiv.innerHTML = `
                <div class="complete-info">
                    <div class="action_complete"></div> <!-- 内容将直接填充 -->
                </div>
            `;
            if (answerElement) {
                answerElement.appendChild(completeDiv);
                const actionCompleteDiv = completeDiv.querySelector('.action_complete');
                const completeContent = content || '智能体已完成任务。'; // 提供默认文本
                // 暂时禁用流式输出，直接进行 Markdown 渲染
                if (actionCompleteDiv) {
                    actionCompleteDiv.innerHTML = marked.parse(completeContent);
                }
            }
        } catch (error) {
            console.error('解析agent完成事件失败:', error);
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
        if (typeof ctx.onComplete === 'function') ctx.onComplete();
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