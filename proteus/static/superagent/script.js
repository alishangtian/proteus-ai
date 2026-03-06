let isProcessing = false; // 标记是否正在处理消息
let eventSource = null; // 用于SSE连接
let chatContainer = null; // 聊天消息容器

// 辅助函数：格式化时间戳，当天显示时分秒，非当天显示年月日时分秒
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    
    // 判断是否为当天
    const isToday = date.getFullYear() === now.getFullYear() &&
                    date.getMonth() === now.getMonth() &&
                    date.getDate() === now.getDate();
    
    if (isToday) {
        // 当天只显示时分秒
        return date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } else {
        // 非当天显示年月日时分秒
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
}

// 读取会话级“工具洞察”开关（与主界面保持一致）
function isToolInsightEnabled() {
    try {
        return sessionStorage.getItem('tool_insight_enabled') === 'true';
    } catch (e) {
        return false;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // 获取聊天容器
    chatContainer = document.getElementById('chatContainer');
    
    // 侧边栏收起/展开功能
    const sidebar = document.getElementById('sidebar');
    const backButton = document.querySelector('.back-button');

    backButton.addEventListener('click', function () {
        console.log('backButton clicked for sidebar toggle');
        sidebar.classList.toggle('collapsed');
        // 旋转收缩按钮
        backButton.style.transform = sidebar.classList.contains('collapsed') ? 'rotate(180deg)' : '';
    });

    // 菜单项点击事件
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(function (item) {
        item.addEventListener('click', function () {
            menuItems.forEach(function (i) {
                i.classList.remove('active');
            });
            item.classList.add('active');
        });
    });

    // 发送消息功能
    const sendButton = document.querySelector('.send-button');
    const inputField = document.querySelector('.input-field');

    sendButton.addEventListener('click', sendMessage);
    inputField.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    async function sendMessage() {
        if (isProcessing) {
            // 如果正在处理中，则调用停止功能
            stopExecution();
            return;
        }

        const text = inputField.value.trim();
        if (!text) return;

        // 禁用输入并切换按钮状态
        inputField.disabled = true;
        sendButton.textContent = '停止';
        sendButton.classList.add('stop');
        isProcessing = true;

        // 创建消息元素 - 使用index.html中的样式结构
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message user-message';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = text;

        // messageContainer.appendChild(messageContent);
        chatContainer.appendChild(messageContainer);

        // 创建回答容器
        const answerElement = document.createElement('div');
        answerElement.className = 'message assistant-message';
        const answerContent = document.createElement('div');
        answerContent.className = 'message-content';
        answerElement.appendChild(answerContent);
        chatContainer.appendChild(answerElement);

        // 重置累积的内容
        currentExplanation = '';
        currentAnswer = '';

        try {
            // 先发送POST请求创建chat会话
            let selectedModel = "agent"; // 默认使用agent模型
            const selectedModelButton = document.querySelector('.model-option.active');
            if (selectedModelButton) {
                selectedModel = selectedModelButton.getAttribute('data-model') || selectedModel;
            }
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text,
                    model: "agent",
                    itecount: 20,
                    memory_enabled: isToolInsightEnabled()
                })
            });

            if (!response.ok) {
                isProcessing = false;
                inputField.disabled = false;
                sendButton.textContent = '发送';
                sendButton.classList.remove('stop');
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '创建会话失败');
            }

            // 保存chat_id并建立WebSocket连接
            currentChatId = result.chat_id;
            const eventSource = new WSEventSource(`${getWsBaseUrl()}/ws/stream/${result.chat_id}`);

            // 处理状态消息
            eventSource.addEventListener('status', event => {
                const message = event.data;
                const statusDiv = document.createElement('div');
                statusDiv.className = 'message-content status-message';
                statusDiv.textContent = message;
                answerElement.querySelector('.message-content').appendChild(statusDiv);
            });

            // 处理工作流事件
            eventSource.addEventListener('workflow', event => {
                currentIteration++; // 每次收到新的工作流事件时增加迭代计数
                try {
                    const workflow = JSON.parse(event.data);
                    const workflowDiv = document.createElement('div');
                    workflowDiv.className = 'tool-use';
                    workflowDiv.innerHTML = `
                        <div class="tool-label">
                            <span class="tool-icon">⚙️</span>
                            工作流已生成: ${workflow.nodes.length} 个节点
                        </div>
                        <input type="text" class="tool-search" value="${JSON.stringify(workflow, null, 2)}">
                        <div class="tool-action">查看</div>
                    `;
                    answerElement.appendChild(workflowDiv);

                    // Add click handler for workflow header
                    const workflowHeader = workflowDiv.querySelector('.workflow-header');
                    if (workflowHeader) {
                        workflowHeader.onclick = function () {
                            workflowDiv.classList.toggle('collapsed');
                        };
                    }
                } catch (error) {
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    errorDiv.textContent = '解析工作流失败';
                    answerElement.appendChild(errorDiv);
                }
            });

            // 处理节点结果
            eventSource.addEventListener('node_result', event => {
                try {
                    const result = JSON.parse(event.data);
                    // 如果当前节点完成，将之前所有运行中的节点标记为完成
                    if (result.status === 'completed') {
                        const runningNodes = answerElement.querySelectorAll('.node-result.running');
                        runningNodes.forEach(node => {
                            node.classList.remove('running');
                            node.classList.add('success');
                            const statusSpan = node.querySelector('.node-header span:last-child');
                            if (statusSpan) {
                                statusSpan.textContent = '执行完成';
                            }
                            const loadingIndicator = node.querySelector('.running-indicator');
                            if (loadingIndicator) {
                                loadingIndicator.remove();
                            }
                        });
                    }
                    renderNodeResult(result, answerElement);
                } catch (error) {
                    answerElement.innerHTML += `<div class="error">解析节点结果失败</div>`;
                }
            });

            // 处理解释说明
            eventSource.addEventListener('explanation', event => {
                try {
                    const response = JSON.parse(event.data);
                    if (response.success && response.data) {
                        currentExplanation += response.data;
                        renderExplanation(currentExplanation, answerElement);
                    } else if (!response.success) {
                        answerElement.innerHTML += `<div class="error">${response.error || '解析解释说明失败'}</div>`;
                    }
                } catch (error) {
                    answerElement.innerHTML += `<div class="error">解析解释说明失败</div>`;
                }
            });

            // 处理直接回答
            eventSource.addEventListener('answer', event => {
                try {
                    const response = JSON.parse(event.data);
                    if (response.success && response.data) {
                        currentAnswer += response.data;
                        renderAnswer(currentAnswer, answerElement);
                    } else if (!response.success) {
                        answerElement.innerHTML += `<div class="error">${response.error || '解析回答失败'}</div>`;
                    }
                } catch (error) {
                    answerElement.innerHTML += `<div class="error">解析回答失败</div>`;
                }
            });

            // 处理工具进度事件
            eventSource.addEventListener('tool_progress', event => {
                try {
                    const data = JSON.parse(event.data);
                    const actionId = data.action_id || currentActionId;
                    // 查找工具结果容器并更新状态
                    const actionGroup = currentActionGroup || answerElement.querySelector(`.action-group[data-action-id="${actionId}"]`);
                    if (actionGroup) {
                        const toolStatus = actionGroup.querySelector('.tool-status');
                        if (toolStatus) {
                            toolStatus.textContent = '执行中';

                            toolStatus.className = 'tool-status running';
                        }
                    }
                } catch (error) {
                    console.error('解析工具进度失败:', error);
                }
            });

            // 处理用户输入请求事件
            eventSource.addEventListener('user_input_required', event => {
                try {
                    const data = JSON.parse(event.data);
                    const inputDiv = document.createElement('div');
                    inputDiv.className = 'user-input-container';

                    // 创建输入表单
                    let inputHtml = `
                        <div class="input-prompt">${data.prompt}</div>
                        <div class="input-form">
                    `;

                    // 根据输入类型创建不同的输入控件
                    switch (data.input_type) {
                        case 'geolocation':
                            inputHtml += `
                                <div class="geolocation-input">
                                    <input type="hidden" class="input-field" id="user-input-${data.node_id}">
                                    <div class="geolocation-status">正在获取位置信息...</div>
                                </div>
                            `;
                            // 自动触发位置获取
                            setTimeout(() => submitUserInput(data.node_id, 'geolocation'), 100);
                            break;
                        case 'local_browser':
                            inputHtml += `
                                <div class="local-browser-input">
                                    <input type="number" class="input-field" id="user-input-${data.node_id}"
                                        placeholder="输入本地浏览器应用端口号"
                                        min="1024"
                                        max="65535"
                                        ${data.validation.required ? 'required' : ''}
                                    />
                                </div>
                            `;
                            break;
                        default: // text
                            inputHtml += `
                                <input type="text" class="input-field" id="user-input-${data.node_id}"
                                    value="${data.default_value || ''}"
                                    ${data.validation.required ? 'required' : ''}
                                    ${data.validation.pattern ? `pattern="${data.validation.pattern}"` : ''}
                                    ${data.validation.min_length ? `minlength="${data.validation.min_length}"` : ''}
                                    ${data.validation.max_length ? `maxlength="${data.validation.max_length}"` : ''}
                                />
                            `;
                    }

                    inputHtml += `
                            <div class="tool-action" onclick="submitUserInput('${data.node_id}', '${data.input_type}','${data.prompt}')">提交</div>
                        </div>
                    `;

                    inputDiv.innerHTML = inputHtml;
                    answerElement.appendChild(inputDiv);

                    // 聚焦到输入框
                    const inputField = document.getElementById(`user-input-${data.node_id}`);
                    if (inputField) {
                        inputField.focus();
                    }
                } catch (error) {
                    console.error('解析用户输入请求失败:', error);
                    answerElement.innerHTML += `<div class="error">解析用户输入请求失败</div>`;
                }
            });

            // 处理工具重试事件
            eventSource.addEventListener('tool_retry', event => {
                try {
                    const data = JSON.parse(event.data);
                    const retryDiv = document.createElement('div');
                    retryDiv.className = 'tool-use retry';
                    retryDiv.innerHTML = `
                        <div class="tool-label">
                            <span class="tool-icon">🔄</span>
                            工具重试: ${data.tool} (${data.attempt}/${data.max_retries})
                        </div>
                        <input type="text" class="tool-search" value="${data.error}">
                        <div class="tool-action">查看</div>
                    `;
                    answerElement.appendChild(retryDiv);
                } catch (error) {
                    console.error('解析工具重试失败:', error);
                }
            });

            // 处理action开始事件
            eventSource.addEventListener('action_start', event => {
                try {
                    const data = JSON.parse(event.data);

                    // 创建新的action组
                    currentActionGroup = document.createElement('div');
                    currentActionGroup.className = 'action-group';
                    currentActionId = data.action_id || Date.now().toString();
                    currentActionGroup.setAttribute('data-action-id', currentActionId);

                    // 将action组添加到答案容器中
                    answerElement.appendChild(currentActionGroup);

                    // 创建action开始元素
                    const startDiv = document.createElement('div');
                    startDiv.setAttribute('data-action-id', currentActionId);
                    startDiv.className = 'tool-use';
                    startDiv.innerHTML = `
                        <div class="tool-label">
                            <span class="tool-icon">⚙️</span>
                            工具: ${data.action}
                        </div>
                        <input type="text" class="tool-search" value="${JSON.stringify(data.input, null, 2)}">
                        <div class="tool-action">查看</div>
                    `;
                    currentActionGroup.appendChild(startDiv);
                } catch (error) {
                    console.error('解析action开始事件失败:', error);
                }
            });

            // 处理action完成事件
            eventSource.addEventListener('action_complete', event => {
                try {
                    const data = JSON.parse(event.data);

                    // 更新工具状态为完成
                    const actionGroup = currentActionGroup || answerElement.querySelector(`.action-group[data-action-id="${data.action_id || currentActionId}"]`);
                    if (!actionGroup) return;

                    // 更新节点状态
                    // 立即更新所有相关节点的状态为完成
                    const allNodes = answerElement.querySelectorAll('.tool-status');
                    console.log(allNodes)
                    allNodes.forEach(node => {
                        if (node.classList.contains('running')) {
                            // 更新状态为完成
                            console.log(node)
                            node.classList.remove('running');
                            node.classList.add('success');
                            node.textContent = '执行完成';
                            const nodeContent = node.querySelector('.node-content');
                            if (nodeContent) {
                                const loadingIndicator = nodeContent.querySelector('.running-indicator');
                                if (loadingIndicator) {
                                    loadingIndicator.remove();
                                }
                                if (data.result) {
                                    nodeContent.innerHTML = typeof data.result === 'string' ? marked.parse(data.result) : `<pre>${JSON.stringify(data.result, null, 2)}</pre>`;
                                }
                            }
                        }
                    });

                    // 检查是否是serper_search类型的action
                    if (data.action === 'serper_search' && typeof data.result === 'object') {
                        // 调用卡片渲染函数
                        const completeDiv = renderSearchResults(data.action, data.result, currentActionId);
                        actionGroup.appendChild(completeDiv);
                    } else {
                        const completeDiv = document.createElement('div');
                        completeDiv.setAttribute('data-action-id', data.action_id || currentActionId);
                        completeDiv.className = 'tool-use completed';
                        completeDiv.innerHTML = `
                            <div class="tool-label">
                                <span class="tool-icon">✓</span>
                                工具完成: ${data.action}
                            </div>
                            <input type="text" class="tool-search" value="${typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2)}">
                            <div class="tool-action">查看</div>
                        `;
                        actionGroup.appendChild(completeDiv);
                    }
                    currentActionGroup = null; // 重置当前action组
                } catch (error) {
                    console.error('解析action完成事件失败:', error);
                }
            });

            // 处理agent开始事件
            // eventSource.addEventListener('agent_start', event => {
            //     try {
            //         const data = JSON.parse(event.data);
            //         const messageDiv = document.createElement('div');
            //         messageDiv.className = 'message assistant-message';
            //         const contentDiv = document.createElement('div');
            //         contentDiv.className = 'message-content';
            //         contentDiv.textContent = `开始处理: ${data.query}`;
            //         messageDiv.appendChild(contentDiv);
            //         answerElement.appendChild(messageDiv);
            //     } catch (error) {
            //         console.error('解析agent开始事件失败:', error);
            //     }
            // });

            // 处理agent思考事件
            eventSource.addEventListener('agent_thinking', event => {
                try {
                    const data = JSON.parse(event.data);
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message assistant-message';
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'message-content';
                    contentDiv.textContent = `${data.thought}`;
                    messageDiv.appendChild(contentDiv);
                    answerElement.appendChild(messageDiv);
                } catch (error) {
                    console.error('解析agent思考事件失败:', error);
                }
            });

            // 处理agent错误事件
            eventSource.addEventListener('agent_error', event => {
                try {
                    const data = JSON.parse(event.data);
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'agent-error';
                    errorDiv.innerHTML = `
                        <div class="error-info">
                            <span class="error-icon">⚠️</span>
                            <span class="error-message">${data.error}</span>
                            <span class="error-timestamp">${formatTimestamp(data.timestamp * 1000)}</span>
                        </div>
                    `;
                    answerElement.appendChild(errorDiv);
                } catch (error) {
                    console.error('解析agent错误事件失败:', error);
                }
            });

            // 处理agent完成事件
            eventSource.addEventListener('agent_complete', event => {
                try {
                    const data = JSON.parse(event.data);
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message assistant-message';
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'message-content';
                    contentDiv.innerHTML = marked.parse(data.result.content || data.result);
                    messageDiv.appendChild(contentDiv);
                    answerElement.appendChild(messageDiv);
                } catch (error) {
                    console.error('解析agent完成事件失败:', error);
                }
            });

            // 处理完成事件
            eventSource.addEventListener('complete', event => {
                try {
                    const result = event.data;
                    const message = result || '完成';
                    const completeDiv = document.createElement('div');
                    completeDiv.className = 'complete';
                    completeDiv.innerHTML = `<div>${message}</div>`;
                    answerElement.appendChild(completeDiv);
                } catch (error) {
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    errorDiv.textContent = '解析完成事件失败';
                    answerElement.appendChild(errorDiv);
                }
                eventSource.close();
                // clearTimeout(timeoutId);
                resetUI();
            });

            // 处理错误
            eventSource.onerror = () => {
                eventSource.close();
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = '连接错误';
                answerElement.appendChild(errorDiv);
                // clearTimeout(timeoutId);
                resetUI();
            };

        } catch (error) {
            console.error('发送消息失败:', error);
            answerElement.innerHTML += `<div class="error">发送消息失败: ${error.message}</div>`;
            resetUI();
        }
    }

    // 工具使用区域的事件委托处理
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('tool-action')) {
            const toolSearch = e.target.closest('.tool-use').querySelector('.tool-search');
            alert(`查看工具使用: ${toolSearch.textContent}`);
        }
    });

    function resetUI() {
        isProcessing = false;
        inputField.disabled = false;
        sendButton.textContent = '发送';
        sendButton.classList.remove('stop');
    }

    function stopExecution() {
        if (eventSource) {
            eventSource.close();
        }
        resetUI();
    }

});