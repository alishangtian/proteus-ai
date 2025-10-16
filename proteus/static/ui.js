// UI 相关的渲染与辅助函数
export let isScrolling = false;
let scrollTimeout = null;

// 用于存储当前正在流式输出的文本内容，以便在后续块到达时追加
let currentStreamedContent = '';
let streamingInterval = null; // 用于控制流式输出的定时器

export function scrollToBottom(conversationHistory) {
    if (isScrolling) return;
    isScrolling = true;
    const lastElement = conversationHistory.lastElementChild;
    if (lastElement) {
        lastElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
        isScrolling = false;
    }, 500);
}

export function resetUI(userInput, sendButton) {
    if (!userInput || !sendButton) return;
    userInput.value = '';
    userInput.disabled = false;
    sendButton.disabled = false;
    sendButton.textContent = '发送';
    sendButton.classList.remove('stop');
    // 重置流式输出状态
    currentStreamedContent = '';
    if (streamingInterval) {
        clearInterval(streamingInterval);
        streamingInterval = null;
    }
}

/**
 * 假流式输出文本内容到指定元素
 * @param {HTMLElement} element 要输出到的 DOM 元素
 * @param {string} text 要流式输出的文本
 * @param {number} delay 每个字符之间的延迟 (毫秒)
 * @param {Function} onComplete 流式输出完成后的回调
 */
export function streamTextContent(element, text, delay = 10, onComplete = () => { }) {
    // 清除之前的流式输出定时器，确保只有一个在运行
    if (streamingInterval) {
        clearInterval(streamingInterval);
        streamingInterval = null;
    }

    element.textContent = ''; // 清空现有内容

    if (!text || text.length === 0) {
        onComplete();
        scrollToBottom(element.closest('#conversation-history')); // 确保在空内容时也滚动到底部
        return;
    }

    let i = 0;
    streamingInterval = setInterval(() => {
        if (i < text.length) {
            element.textContent += text.charAt(i);
            i++;
            scrollToBottom(element.closest('#conversation-history')); // 确保滚动到底部
        } else {
            clearInterval(streamingInterval);
            streamingInterval = null;
            onComplete();
        }
    }, delay);
    scrollToBottom(element.closest('#conversation-history')); // 确保在流式输出开始时也滚动到底部
}


export function renderNodeResult(data, container, currentIteration = 1) {
    // 优化：所有节点结果尽量以 Markdown 渲染
    // - 如果 data.error 存在，使用 Markdown 显示错误信息（加粗 + code block）
    // - 如果 data.data 为字符串，直接交给 marked.parse 解析（支持 Markdown）
    // - 如果 data.data 为对象/数组，先转为 JSON，再包装成 ```json code fence 交给 marked.parse 渲染
    // - 运行中保持运行指示器样式
    let statusClass = '';
    let statusText = '';
    let content = '';

    try {
        if (data.error) {
            statusClass = 'error';
            statusText = '执行失败';
            const md = `**错误**\n\n\`\`\`\n${data.error}\n\`\`\``;
            content = marked.parse(md);
        } else {
            switch (data.status) {
                case 'running':
                    if (data.iteration && data.iteration < currentIteration) {
                        statusClass = 'success';
                        statusText = '执行完成';
                        if (data.data) {
                            if (typeof data.data === 'string') {
                                content = marked.parse(data.data);
                            } else {
                                const md = "```json\n" + JSON.stringify(data.data, null, 2) + "\n```";
                                content = marked.parse(md);
                            }
                        } else {
                            content = '';
                        }
                    } else if (data.completed) {
                        statusClass = 'success';
                        statusText = '执行完成';
                        if (data.data) {
                            if (typeof data.data === 'string') {
                                content = marked.parse(data.data);
                            } else {
                                const md = "```json\n" + JSON.stringify(data.data, null, 2) + "\n```";
                                content = marked.parse(md);
                            }
                        }
                    } else {
                        statusClass = 'running';
                        statusText = '执行中';
                        content = '<div class="running-indicator"></div>';
                    }
                    break;
                case 'completed':
                    statusClass = 'success';
                    statusText = '执行完成';
                    if (data.data) {
                        if (typeof data.data === 'string') {
                            content = marked.parse(data.data);
                        } else {
                            const md = "```json\n" + JSON.stringify(data.data, null, 2) + "\n```";
                            content = marked.parse(md);
                        }
                    } else {
                        content = '';
                    }
                    break;
                default:
                    statusClass = '';
                    statusText = data.status || '未知状态';
                    content = data.data ? (typeof data.data === 'string' ? marked.parse(data.data) : marked.parse("```json\n" + JSON.stringify(data.data, null, 2) + "\n```")) : '';
            }
        }
    } catch (err) {
        // 如果 marked 渲染出问题，降级为简单文本显示
        console.warn('renderNodeResult: Markdown 渲染失败，降级为纯文本', err);
        content = `<pre>${typeof data.data === 'string' ? data.data : JSON.stringify(data.data, null, 2)}</pre>`;
    }

    const existingNode = container.querySelector(`[data-node-id="${data.node_id}"]`);
    if (existingNode) {
        existingNode.className = `node-result ${statusClass}`;
        const wasCollapsed = existingNode.classList.contains('collapsed');
        existingNode.innerHTML = `
            <div class="node-header">
                <span>节点: ${data.node_id}</span>
                <span>${statusText}</span>
            </div>
            <div class="node-content">${content}</div>
        `;
        if (wasCollapsed || data.status === 'completed') {
            existingNode.classList.add('collapsed');
        }
    } else {
        const nodeDiv = document.createElement('div');
        nodeDiv.className = `node-result ${statusClass}`;
        nodeDiv.setAttribute('data-node-id', data.node_id);
        nodeDiv.innerHTML = `
            <div class="node-header">
                <span>节点: ${data.node_id}</span>
                <span>${statusText}</span>
            </div>
            <div class="node-content">${content}</div>
        `;
        // 默认折叠，除非状态是 'running'
        if (data.status !== 'running') {
            nodeDiv.classList.add('collapsed');
        }
        container.appendChild(nodeDiv);
    }

    const nodeHeader = container.querySelector(`[data-node-id="${data.node_id}"] .node-header`);
    if (nodeHeader) {
        nodeHeader.onclick = function (e) {
            e.stopPropagation();
            const nodeResult = this.closest('.node-result');
            nodeResult.classList.toggle('collapsed');
            // 强制触发重绘以避免动画问题
            nodeResult.style.display = 'none';
            nodeResult.offsetHeight;
            nodeResult.style.display = '';
        };
    }
}

export function renderExplanation(content, container) {
    let explanationDiv = container.querySelector('.explanation');
    if (!explanationDiv) {
        explanationDiv = document.createElement('div');
        explanationDiv.className = 'explanation';
        container.appendChild(explanationDiv);
    }
    const htmlContent = marked.parse(content);
    explanationDiv.innerHTML = htmlContent;
}

export function renderAnswer(content, container, isFinal = false) {
    let answerDiv = container.querySelector('.answer:last-child');
    if (!answerDiv) {
        answerDiv = document.createElement('div');
        answerDiv.className = 'answer';
        container.appendChild(answerDiv);
    }

    // 累积内容
    currentStreamedContent += content;

    // 如果是最终块，则进行 Markdown 渲染并替换内容
    if (isFinal) {
        if (streamingInterval) {
            clearInterval(streamingInterval);
            streamingInterval = null;
        }
        answerDiv.innerHTML = marked.parse(currentStreamedContent);
        currentStreamedContent = ''; // 重置累积内容
    } else {
        // 否则，进行流式输出
        streamTextContent(answerDiv, currentStreamedContent);
    }
}

export function createQuestionElement(text, currentModel) {
    const questionElement = document.createElement('div');
    questionElement.className = 'history-item';
    if (currentModel) {
        questionElement.setAttribute('data-model', currentModel);
    }

    const qaContainer = document.createElement('div');
    qaContainer.className = 'qa-container';

    const questionDiv = document.createElement('div');
    questionDiv.className = 'question';
    questionDiv.textContent = text;

    const copyBtn = document.createElement('div');
    copyBtn.className = 'copy-btn';
    copyBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" class="copy-icon">
            <path fill="currentColor" d="M19,21H8V7H19M19,5H8A2,2 0 0,0 6,7V21A2,2 0 0,0 8,23H19A2,2 0 0,0 21,21V7A2,2 0 0,0 19,5M16,1H4A2,2 0 0,0 2,3V17H4V3H16V1Z"/>
        </svg>
        <span class="copy-tooltip">复制</span>
    `;
    questionDiv.insertBefore(copyBtn, questionDiv.firstChild);

    qaContainer.appendChild(questionDiv);

    const answerElement = document.createElement('div');
    answerElement.className = 'answer';
    qaContainer.appendChild(answerElement);

    questionElement.appendChild(qaContainer);
    return { questionElement, answerElement, questionDiv };
}
export function updatePlaybook(tasks) {
    const playbookContainer = document.getElementById('playbook-container');
    const playbookContent = document.getElementById('playbook-content');
    
    if (tasks && tasks.length > 0) {
        // 构建任务列表 HTML，每个任务前添加圆形状态指示器
        let html = '<ul class="playbook-task-list">';
        tasks.forEach(task => {
            const statusClass = task.status === '已完成' ? 'completed' : 'pending';
            
            html += `
                <li class="playbook-task-item ${statusClass}">
                    <div class="task-indicator ${statusClass}"></div>
                    <span class="task-description">${task.description}</span>
                </li>
            `;
        });
        html += '</ul>';
        
        playbookContent.innerHTML = html;
        playbookContainer.style.display = 'flex';
    } else {
        playbookContent.innerHTML = '';
        playbookContainer.style.display = 'none';
    }
}