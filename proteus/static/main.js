import Icons from './icons.js';

// 临时存储历史对话数据 {model: htmlContent}
const historyStorage = {};
// 临时存储工具调用数据 {model: toolExecutions}
const toolExecutionsStorage = {};
// 工具执行数据存储
const toolExecutions = {};
// 菜单栏收起/展开功能
document.addEventListener('DOMContentLoaded', function () {
    // 添加菜单项点击事件
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function () {
            document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
            this.classList.add('active');
        });
    });

    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.querySelector('.toggle-sidebar');

    // 默认保持菜单栏展开状态
    sidebar.classList.remove('collapsed');

    // 切换按钮点击事件
    toggleBtn.addEventListener('click', function () {
        sidebar.classList.toggle('collapsed');
        // 保存状态到本地存储
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
});


// 存储当前chat_id和处理状态的全局变量
let currentChatId = null;
let isProcessing = false;
let currentModel = null; // 当前选择的菜单模式
const showIterationModels = ["super-agent", "home", "mcp-agent", "multi-agent", "browser-agent", "deep-research"];
// 提交用户输入的全局函数
async function submitUserInput(nodeId, inputType, prompt) {
    const inputField = document.getElementById(`user-input-${nodeId}`);
    if (!inputField) return;

    let value = inputField.value;
    if (!currentChatId) {
        console.error('No chat ID available');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = '提交失败: 无法获取会话ID';
        inputField.parentElement.appendChild(errorDiv);
        return;
    }

    // 根据输入类型转换值
    try {
        switch (inputType) {
            case 'boolean':
                value = value === 'true';
                break;
            case 'number':
                value = Number(value);
                if (isNaN(value)) throw new Error('Invalid number');
                break;
            case 'json':
                value = JSON.parse(value);
                break;
            case 'local_browser':
                // 对于 local_browser 类型，发送请求到本地服务
                const port = value;
                const submitButton = inputField.parentElement.querySelector('.submit-input');

                // 立即禁用输入框和提交按钮
                inputField.disabled = true;
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.textContent = '处理中...';
                }

                try {
                    const response = await fetch(`http://localhost:${port}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            task: prompt
                        })
                    });
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const browser_result = await response.json();
                    console.log(browser_result);
                    // 发送结果到后端
                    fetch('/user_input', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            node_id: nodeId,
                            value: browser_result['result'],
                            chat_id: currentChatId
                        })
                    }).then(response => {
                        if (!response.ok) {
                            throw new Error('提交失败');
                        }
                        // 提交成功后禁用输入框和提交按钮
                        inputField.disabled = true;
                        if (submitButton) {
                            submitButton.disabled = true;
                            submitButton.classList.add('submitted');
                            submitButton.textContent = '已提交';
                        }
                    }).catch(error => {
                        console.error('提交位置信息失败:', error);
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'error';
                        errorDiv.textContent = `提交失败: ${error.message}`;
                        inputField.parentElement.appendChild(errorDiv);
                        // 恢复提交按钮状态
                        if (submitButton) {
                            submitButton.disabled = false;
                            submitButton.textContent = '提交';
                        }
                    });
                    return;
                } catch (error) {
                    console.error('本地浏览器请求失败:', error);
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    errorDiv.textContent = `本地浏览器请求失败: ${error.message}`;
                    inputField.parentElement.appendChild(errorDiv);

                    // 对于连接错误，允许继续修改端口号并重试
                    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                        if (submitButton) {
                            submitButton.disabled = false;
                            submitButton.textContent = '提交';
                        }
                        inputField.disabled = false;
                    }
                    return;
                }
                break;
            case 'geolocation':
                // 对于 geolocation 类型，自动获取位置信息
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        (position) => {
                            // 构造位置数据
                            const locationData = {
                                latitude: position.coords.latitude,
                                longitude: position.coords.longitude,
                                accuracy: position.coords.accuracy,
                                timestamp: position.timestamp
                            };

                            // 更新界面状态
                            const container = inputField.closest('.geolocation-input');
                            if (container) {
                                const statusDiv = container.querySelector('.geolocation-status');
                                if (statusDiv) {
                                    statusDiv.innerHTML = `
                                        <div class="success">
                                            <div class="location-status">
                                                <span class="success-icon">✓</span>
                                                <span>位置信息获取成功</span>
                                            </div>
                                            <div class="location-details">
                                                <div class="coordinate-item">
                                                    <span class="coordinate-label">纬度:</span>
                                                    <span class="coordinate-value">${position.coords.latitude.toFixed(6)}°</span>
                                                </div>
                                                <div class="coordinate-item">
                                                    <span class="coordinate-label">经度:</span>
                                                    <span class="coordinate-value">${position.coords.longitude.toFixed(6)}°</span>
                                                </div>
                                                <div class="coordinate-item">
                                                    <span class="coordinate-label">精确度:</span>
                                                    <span class="coordinate-value">${position.coords.accuracy.toFixed(2)} 米</span>
                                                </div>
                                            </div>
                                        </div>
                                    `;
                                    // 移除提交按钮
                                    const submitButton = container.nextElementSibling;
                                    if (submitButton) {
                                        submitButton.remove();
                                    }
                                }
                            }

                            // 自动发送位置数据到后端
                            fetch('/user_input', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    node_id: nodeId,
                                    value: locationData,
                                    chat_id: currentChatId
                                })
                            }).then(response => {
                                if (!response.ok) {
                                    throw new Error('提交失败');
                                }
                                // 提交成功后禁用输入框和提交按钮
                                inputField.disabled = true;
                                const submitButton = inputField.parentElement.querySelector('.submit-input');
                                if (submitButton) {
                                    submitButton.disabled = true;
                                    submitButton.classList.add('submitted');
                                    submitButton.textContent = '已提交';
                                }
                            }).catch(error => {
                                console.error('提交位置信息失败:', error);
                                const errorDiv = document.createElement('div');
                                errorDiv.className = 'error';
                                errorDiv.textContent = `提交失败: ${error.message}`;
                                inputField.parentElement.appendChild(errorDiv);
                            });
                        },
                        (error) => {
                            console.error('获取位置信息失败:', error);
                            const errorDiv = document.createElement('div');
                            errorDiv.className = 'error';
                            errorDiv.textContent = `获取位置信息失败: ${error.message}`;
                            inputField.parentElement.appendChild(errorDiv);
                        }
                    );
                    return; // 提前返回，因为位置获取是异步的
                } else {
                    throw new Error('浏览器不支持地理位置功能');
                }
                break;
        }

        // 发送用户输入到后端
        fetch('/user_input', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                node_id: nodeId,
                value: value,
                chat_id: currentChatId
            })
        }).then(response => {
            if (!response.ok) {
                throw new Error('提交失败');
            }
            // 提交成功后禁用输入框和提交按钮
            inputField.disabled = true;
            const submitButton = inputField.parentElement.querySelector('.submit-input');
            if (submitButton) {
                submitButton.disabled = true;
            }
        }).catch(error => {
            console.error('提交用户输入失败:', error);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = `提交失败: ${error.message}`;
            inputField.parentElement.appendChild(errorDiv);
        });
    } catch (error) {
        console.error('输入值转换失败:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = `输入值格式错误: ${error.message}`;
        inputField.parentElement.appendChild(errorDiv);
    }
}

// 使用事件委托处理复制按钮点击
document.addEventListener('click', function (e) {
    if (e.target.closest('.copy-btn')) {
        const copyBtn = e.target.closest('.copy-btn');
        const container = copyBtn.closest('.question, .tool-result, .result-value');

        // 获取要复制的文本
        let textToCopy = '';
        if (container.classList.contains('result-value')) {
            // 处理工具结果区域的复制
            const resultContent = container.querySelector('pre') || container;
            // 获取结果内容div中的文本
            const contentDiv = container.querySelector('.result-content');
            textToCopy = contentDiv ? contentDiv.textContent.trim() : '';
        } else {
            // 处理问题和普通结果的复制
            textToCopy = Array.from(container.childNodes)
                .filter(node => node.nodeType === Node.TEXT_NODE)
                .map(node => node.textContent.trim())
                .join(' ').trim();
        }

        navigator.clipboard.writeText(textToCopy).then(() => {
            const tooltip = copyBtn.querySelector('.copy-tooltip');
            tooltip.textContent = '复制成功';
            setTimeout(() => {
                tooltip.textContent = '复制';
            }, 2000);
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // 添加页面刷新前的处理
    window.addEventListener('beforeunload', (event) => {
        if (isProcessing && currentChatId) {
            event.preventDefault();
            event.returnValue = '';

            // 同步方式停止agent
            fetch(`/stop/${document.querySelector('.menu-item.model-option.active').getAttribute('data-model')}/${currentChatId}`, {
                method: 'GET',
                // 使用同步XHR确保在页面刷新前完成
                async: false
            });

            return event.returnValue;
        }
    });

    // 添加菜单项点击事件
    const modelOptions = document.querySelectorAll('.menu-item.model-option');
    const itecountContainer = document.getElementById('itecount-container');

    // 更新轮次显示状态
    function updateIterationDisplay(selectedItem) {
        const local_model = selectedItem.getAttribute('data-model');
        if (showIterationModels.includes(local_model)) {
            itecountContainer.style.display = 'inline-block';
        } else {
            itecountContainer.style.display = 'none';
        }
    }

    // 初始化显示状态 - 只选中首页选项
    document.querySelectorAll('.menu-item').forEach(item => {
        item.classList.remove('active');
        if (item.classList.contains("home-page")) {
            item.classList.add('active');
            updateIterationDisplay(item);
            currentModel = item.getAttribute('data-model');
        }
    });

    modelOptions.forEach(item => {
        item.addEventListener('click', function () {
            const newModel = this.getAttribute('data-model');

            // 检查是否是创建智能体菜单项
            if (newModel === 'create-agent') {
                window.location.href = '/agent-page';
                return;
            }

            // 0. 隐藏工具执行详情弹框
            const detailsContainer = document.querySelector('.tool-details-container');
            if (detailsContainer) {
                detailsContainer.classList.remove('visible');
            }

            // 1. 存储当前对话历史
            const conversationHistory = document.getElementById('conversation-history');
            if (currentModel && conversationHistory.children.length > 0) {
                historyStorage[currentModel] = conversationHistory.innerHTML;
            }

            // 2. 存储当前工具调用信息
            const toolsListElement = document.querySelector('.tools-list');
            const toolsListHTML = toolsListElement.innerHTML;
            if (currentModel) {
                toolExecutionsStorage[currentModel] = toolsListHTML;
            }

            // 3. 清空当前对话历史
            conversationHistory.innerHTML = '';

            // 4. 清空当前工具调用信息
            toolsListElement.innerHTML = '';

            // 重置工具数量
            const toolsCountSpan = document.querySelector('.tools-count');
            toolsCountSpan.textContent = 0;

            // 5. 恢复新模型的对话历史(如果存在)
            if (historyStorage[newModel]) {
                conversationHistory.innerHTML = historyStorage[newModel];
            }

            // 6. 恢复新模型的工具调用信息(如果存在)
            if (toolExecutionsStorage[newModel]) {
                const toolsContent = toolExecutionsStorage[newModel];
                toolsListElement.innerHTML = toolsContent;
                const tool_count = toolsListElement.querySelectorAll('.tool-item').length;
                toolsCountSpan.textContent = tool_count;
                // 重新绑定工具列表项点击事件
                document.querySelectorAll('.tool-item').forEach(item => {
                    const actionId = item.getAttribute('data-action-id');
                    item.querySelector('.view-details-btn').addEventListener('click', (e) => {
                        e.stopPropagation();
                        const detailsContainer = document.querySelector('.tool-details-container');
                        detailsContainer.classList.add('visible');

                        const detailsContent = document.querySelector('.tool-details-content');
                        const execution = toolExecutions[actionId];

                        // 实时构建详情内容，与action_start中保持一致
                        let resultContent = '执行中...';
                        let metricsContent = `
                            <div class="metric">
                                <span class="metric-label">开始时间:</span>
                                <span class="metric-value">${new Date(execution.startTime).toLocaleTimeString()}</span>
                            </div>
                        `;

                        if (execution.status === 'completed') {
                            resultContent = `<pre>${typeof execution.result === 'string' ?
                                execution.result : JSON.stringify(execution.result, null, 2)}</pre>`;
                            metricsContent += `
                                <div class="metric">
                                    <span class="metric-label">结束时间:</span>
                                    <span class="metric-value">${new Date(execution.endTime).toLocaleTimeString()}</span>
                                </div>
                                <div class="metric">
                                    <span class="metric-label">执行耗时:</span>
                                    <span class="metric-value">${(execution.duration).toFixed(2)}ms</span>
                                </div>
                            `;
                        } else {
                            metricsContent += `
                                <div class="metric">
                                    <span class="metric-label">已执行:</span>
                                    <span class="metric-value">${Date.now() - execution.startTime}ms</span>
                                </div>
                            `;
                        }

                        detailsContent.innerHTML = `
                            <div class="tool-params-section">
                                <div class="tool-param">
                                    <div class="tool-param-label">工具名称</div>
                                    <div class="tool-param-value">${execution.action}</div>
                                </div>
                                <div class="tool-param">
                                    <div class="tool-param-label">参数</div>
                                    <div class="tool-param-value"><pre>${JSON.stringify(execution.input, null, 2)}</pre></div>
                                </div>
                            </div>
                            <div class="tool-result-section">
                                <div class="tool-result">
                                    <div class="result-label">执行结果</div>
                                    <div class="result-value">
                                        <div class="result-content">${resultContent}</div>
                                    </div>
                                </div>
                                <div class="tool-metrics">
                                    ${metricsContent}
                                </div>
                            </div>
                        `;

                        // 关闭按钮事件
                        detailsContainer.querySelector('.close-details').addEventListener('click', () => {
                            detailsContainer.classList.remove('visible');
                        });
                    });
                });
            }

            // 更新UI状态
            document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
            this.classList.add('active');
            currentModel = newModel;
            updateIterationDisplay(this);
        });
    });

    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const conversationHistory = document.getElementById('conversation-history');

    // 用于存储累积的内容
    let currentExplanation = '';
    let currentAnswer = '';
    let currentActionGroup = null;
    let currentActionId = null;
    let currentIteration = 1; // 当前迭代计数

    // 自动滚动到底部的函数
    let isScrolling = false;
    let scrollTimeout = null;
    marked.use({
        gfm: true,
        tables: true,
        breaks: false,      // 禁用自动换行转换
        pedantic: false,
        smartLists: true,
        smartypants: false, // 禁用智能标点转换
        gfm: true,
        breaks: true,
        baseUrl: null,
        xhtml: false,
        xhtml: true,
        mangle: false,
        headerIds: false,
        headerPrefix: '',
        langPrefix: 'hljs ', // 调整语言前缀匹配highlight.js
        sanitize: false,     // 保留原始HTML
        highlight: (code, lang) => {
            try {
                return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
            } catch (e) {
                return hljs.highlightAuto(code).value;
            }
        },
        baseUrl: null,
        listItemIndent: '1' // 规范列表缩进
    });

    function scrollToBottom() {
        if (isScrolling) return;

        isScrolling = true;
        const lastElement = conversationHistory.lastElementChild;
        if (lastElement) {
            lastElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }

        // 设置滚动冷却时间
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            isScrolling = false;
        }, 500); // 500ms内不重复滚动
    }

    // 事件处理
    sendButton.addEventListener('click', () => {
        sendMessage();
        scrollToBottom();
    });

    userInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Shift+Enter 插入换行
                return;
            } else {
                // 单独Enter 发送消息
                e.preventDefault();
                sendMessage();
                scrollToBottom();
            }
        }
    });

    // 重置UI
    function resetUI() {
        userInput.value = '';
        userInput.disabled = false;
        sendButton.disabled = false;
        sendButton.textContent = '发送';
        sendButton.classList.remove('stop');
        isProcessing = false;
        userInput.focus();
    }

    // 渲染节点结果
    function renderNodeResult(data, container) {
        // 根据状态设置样式类和文本
        let statusClass = '';
        let statusText = '';
        let content = '';

        // 首先检查error是否存在
        if (data.error) {
            statusClass = 'error';
            statusText = '执行失败';
            content = `<div class="error">${data.error}</div>`;
        } else {
            // 如果没有error，则根据status判断
            switch (data.status) {
                case 'running':
                    // 如果是上一个迭代的节点或已完成的节点，显示为completed
                    if (data.iteration && data.iteration < currentIteration) {
                        statusClass = 'success';
                        statusText = '执行完成';
                        content = data.data ? (typeof data.data === 'string' ? marked.parse(data.data) : `<pre>${JSON.stringify(data.data, null, 2)}</pre>`) : '';
                    } else if (data.completed) {
                        statusClass = 'success';
                        statusText = '执行完成';
                        content = data.data ? (typeof data.data === 'string' ? marked.parse(data.data) : `<pre>${JSON.stringify(data.data, null, 2)}</pre>`) : '';
                    } else {
                        statusClass = 'running';
                        statusText = '执行中';
                        content = '<div class="running-indicator"></div>';
                    }
                    break;
                case 'completed':
                    statusClass = 'success';
                    statusText = '执行完成';
                    content = data.data ? `<pre>${JSON.stringify(data.data, null, 2)}</pre>` : '';
                    break;
                default:
                    statusClass = '';
                    statusText = data.status || '未知状态';
                    content = '';
            }
        }

        // 查找是否已存在相同节点的div
        const existingNode = container.querySelector(`[data-node-id="${data.node_id}"]`);
        if (existingNode) {
            // 更新现有节点
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
            // 创建新节点
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
            // 默认展开结果容器
            nodeDiv.classList.remove('collapsed');
            container.appendChild(nodeDiv);
        }

        // 添加可靠的点击事件处理
        const nodeHeader = container.querySelector(`[data-node-id="${data.node_id}"] .node-header`);
        if (nodeHeader) {
            nodeHeader.onclick = function (e) {
                e.stopPropagation();
                const nodeResult = this.closest('.node-result');
                nodeResult.classList.toggle('collapsed');

                // 强制重绘以确保动画效果
                nodeResult.style.display = 'none';
                nodeResult.offsetHeight; // trigger reflow
                nodeResult.style.display = '';
            };
        }
    }

    // 渲染解释说明
    function renderExplanation(content, container) {
        // 查找或创建explanation div
        let explanationDiv = container.querySelector('.explanation');
        if (!explanationDiv) {
            explanationDiv = document.createElement('div');
            explanationDiv.className = 'explanation';
            container.appendChild(explanationDiv);
        }
        // 使用累积的内容更新div
        const htmlContent = marked.parse(content);
        explanationDiv.innerHTML = htmlContent;
    }

    // 渲染回答
    function renderAnswer(content, container) {
        // 查找或创建answer div
        let answerDiv = container.querySelector('.answer:last-child');
        if (!answerDiv) {
            answerDiv = document.createElement('div');
            answerDiv.className = 'answer';
            container.appendChild(answerDiv);
        }
        // 使用累积的内容更新div
        const htmlContent = marked.parse(content);
        answerDiv.innerHTML = htmlContent;
    }

    // 停止执行的函数
    async function stopExecution() {
        if (!currentChatId) return;

        const selectedModelButton = document.querySelector('.model-option.active');
        const selectedModel = selectedModelButton.getAttribute('data-model');

        try {
            const response = await fetch(`/stop/${selectedModel}/${currentChatId}`, {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '停止执行失败');
            }

            // 添加停止执行的状态消息
            const answerElement = document.querySelector('.answer:last-child');
            if (answerElement) {
                const stopMessage = document.createElement('div');
                stopMessage.className = 'status-message';
                stopMessage.textContent = '已停止执行';
                answerElement.appendChild(stopMessage);
            }

            // 重置UI状态
            resetUI();
        } catch (error) {
            console.error('停止执行失败:', error);
            // 显示错误消息
            const answerElement = document.querySelector('.answer:last-child');
            if (answerElement) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = `停止执行失败: ${error.message}`;
                answerElement.appendChild(errorDiv);
            }
            // 仍然重置UI状态，以防止界面卡在停止状态
            resetUI();
        }
    }

    // 发送消息
    async function sendMessage() {
        if (isProcessing) {
            // 如果正在处理中，则调用停止功能
            stopExecution();
            return;
        }

        const text = userInput.value.trim();
        if (!text) return;

        // 禁用输入并切换按钮状态
        userInput.disabled = true;
        sendButton.textContent = '停止';
        sendButton.classList.add('stop');
        isProcessing = true;

        // 创建消息元素
        const questionElement = document.createElement('div');
        questionElement.className = 'history-item';
        if (currentModel) {
            questionElement.setAttribute('data-model', currentModel); // 设置当前model
        }

        // 创建qa-container
        const qaContainer = document.createElement('div');
        qaContainer.className = 'qa-container';

        // 添加问题
        const questionDiv = document.createElement('div');
        questionDiv.className = 'question';
        questionDiv.textContent = text;
        qaContainer.appendChild(questionDiv);

        // 添加回答容器
        const answerElement = document.createElement('div');
        answerElement.className = 'answer';
        qaContainer.appendChild(answerElement);

        // 添加复制按钮到左侧
        const copyBtn = document.createElement('div');
        copyBtn.className = 'copy-btn';
        copyBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" class="copy-icon">
                <path fill="currentColor" d="M19,21H8V7H19M19,5H8A2,2 0 0,0 6,7V21A2,2 0 0,0 8,23H19A2,2 0 0,0 21,21V7A2,2 0 0,0 19,5M16,1H4A2,2 0 0,0 2,3V17H4V3H16V1Z"/>
            </svg>
            <span class="copy-tooltip">复制</span>
        `;
        questionDiv.insertBefore(copyBtn, questionDiv.firstChild);

        // 将qa-container添加到history-item
        questionElement.appendChild(qaContainer);

        conversationHistory.appendChild(questionElement);

        // 重置累积的内容
        currentExplanation = '';
        currentAnswer = '';

        try {
            // 先发送POST请求创建chat会话
            const selectedModelButton = document.querySelector('.menu-item.model-option.active');
            if (!selectedModelButton) {
                console.error('未选择模型');
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = '请先选择模型';
                answerElement.appendChild(errorDiv);
                resetUI();
                return;
            }
            const selectedModel = selectedModelButton.getAttribute('data-model');

            let response;
            if (selectedModel === 'multi-agent') {
                // 多智能体模式使用 /agents/route 接口
                response = await fetch('/agents/route', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: text,
                        max_iterations: parseInt(document.getElementById('itecount').value) || 10,
                        stream: true
                    })
                });
            } else {
                // 其他模式使用 /chat 接口
                response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        text,
                        model: selectedModel,
                        itecount: showIterationModels.includes(selectedModel) ? parseInt(document.getElementById('itecount').value) : undefined
                    })
                });
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '创建会话失败');
            }

            // 保存chat_id并建立SSE连接
            currentChatId = result.chat_id;
            const eventSource = new EventSource(`stream/${result.chat_id}`);

            // 超时处理
            // const timeoutId = setTimeout(() => {
            //     eventSource.close();
            //     answerElement.innerHTML += `<div class="error">请求超时</div>`;
            //     resetUI();
            // }, 600000);

            // 处理智能体选择事件
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
                    answerElement.appendChild(selectionDiv);
                } catch (error) {
                    console.error('解析智能体选择事件失败:', error);
                }
            });

            // 处理智能体执行事件
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
                                            <span class="detail-value">${data.execution_data.tools.map(t => `<span class="tool-tag">${t}</span>`).join('')}</span>
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
                                            <div class="detail-value result-content">${marked.parse(data.execution_data.result || '')}</div>
                                        </div>
                                        <div class="agent-detail">
                                            <span class="detail-label">状态:</span>
                                            <span class="detail-value">${data.execution_data.status}</span>
                                        </div>
                                    </div>
                                    <div class="agent-footer">
                                        <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                                    </div>
                                </div>
                            </div>`;
                    }

                    executionDiv.innerHTML = executionContent;
                    answerElement.appendChild(executionDiv);
                } catch (error) {
                    console.error('解析智能体执行事件失败:', error);
                }
            });

            // 处理状态消息
            eventSource.addEventListener('status', event => {
                const message = event.data;
                const statusDiv = document.createElement('div');
                statusDiv.className = 'status-message';
                statusDiv.textContent = message;
                answerElement.appendChild(statusDiv);
            });

            // 处理工作流事件
            eventSource.addEventListener('workflow', event => {
                currentIteration++; // 每次收到新的工作流事件时增加迭代计数
                try {
                    const workflow = JSON.parse(event.data);
                    const workflowDiv = document.createElement('div');
                    workflowDiv.className = 'workflow-info collapsed';
                    workflowDiv.innerHTML = `
                        <div class="workflow-header">
                            <span>工作流已生成: ${workflow.nodes.length} 个节点</span>
                        </div>
                        <div class="workflow-content">
                            <pre>${JSON.stringify(workflow, null, 2)}</pre>
                        </div>
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
                    currentActionId = actionId; // 更新当前actionId

                    // 查找或创建action group
                    // let actionGroup = answerElement.querySelector(`.action-group[data-action-id="${actionId}"]`);
                    // if (!actionGroup) {
                    //     actionGroup = document.createElement('div');
                    //     actionGroup.className = 'action-group';
                    //     actionGroup.setAttribute('data-action-id', actionId);
                    //     answerElement.appendChild(actionGroup);
                    //     currentActionGroup = actionGroup;
                    // }

                    // 更新工具状态
                    // const toolStatus = actionGroup.querySelector('.tool-status');
                    // if (toolStatus) {
                    //     toolStatus.textContent = `执行中 (${data.progress || 0}%)`;
                    //     toolStatus.className = 'tool-status running';
                    // } else {
                    //     actionGroup.innerHTML = `
                    //         <div class="tool-header">
                    //             <span class="tool-name">${data.action || '工具执行'}</span>
                    //             <span class="tool-status running">执行中 (${data.progress || 0}%)</span>
                    //         </div>
                    //         <div class="tool-details"></div>
                    //     `;
                    // }
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
                                <div class="geolocation-input" style="display:none">
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
                        case 'password':
                            inputHtml += `
                                <input type="password" class="input-field" id="user-input-${data.node_id}"
                                    value="${data.default_value || ''}"
                                    ${data.validation.required ? 'required' : ''}
                                    ${data.validation.pattern ? `pattern="${data.validation.pattern}"` : ''}
                                    ${data.validation.min_length ? `minlength="${data.validation.min_length}"` : ''}
                                    ${data.validation.max_length ? `maxlength="${data.validation.max_length}"` : ''}
                                />
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
                            <button class="submit-input" data-node-id="${data.node_id}" data-input-type="${data.input_type}" data-prompt="${data.prompt}">提交</button>
                        </div>
                    `;

                    inputDiv.innerHTML = inputHtml;
                    answerElement.appendChild(inputDiv);

                    // 为提交按钮添加事件监听
                    const submitButton = inputDiv.querySelector('.submit-input');
                    if (submitButton) {
                        submitButton.addEventListener('click', () => {
                            const nodeId = submitButton.getAttribute('data-node-id');
                            const inputType = submitButton.getAttribute('data-input-type');
                            const prompt = submitButton.getAttribute('data-prompt');
                            submitUserInput(nodeId, inputType, prompt);
                        });
                    }

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
                    retryDiv.className = 'tool-retry';
                    retryDiv.innerHTML = `
                        <div class="retry-info">
                            <span>工具 ${data.tool} 重试中 (${data.attempt}/${data.max_retries})</span>
                            <span class="retry-error">${data.error}</span>
                        </div>
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
                    const actionId = data.action_id || Date.now().toString();
                    currentActionId = actionId; // 同时更新全局变量

                    // 如果是file_write动作，自动下载文件
                    if (data.action === 'file_write') {
                        const input = data.input;

                        // 规范化文件名
                        const sanitizeFilename = (name) => {
                            return name.replace(/[^a-zA-Z0-9\u4e00-\u9fa5\-_]/g, '_')
                                .replace(/_+/g, '_')
                                .replace(/^_+|_+$/g, '');
                        };

                        // 确定文件类型和MIME类型
                        const getMimeType = (format) => {
                            const mimeTypes = {
                                'txt': 'text/plain',
                                'csv': 'text/csv',
                                'json': 'application/json',
                                'xml': 'application/xml',
                                'pdf': 'application/pdf',
                                'jpg': 'image/jpeg',
                                'jpeg': 'image/jpeg',
                                'png': 'image/png',
                                'gif': 'image/gif',
                                'html': 'text/html',
                                'js': 'application/javascript',
                                'css': 'text/css'
                            };
                            return mimeTypes[format.toLowerCase()] || 'application/octet-stream';
                        };

                        // 生成规范化的文件名
                        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                        const baseName = sanitizeFilename(input.filename || 'file');
                        const extension = (input.format || 'txt').toLowerCase();
                        const fileName = `${baseName}_${timestamp}.${extension}`;

                        // 创建并下载文件
                        const blob = new Blob([input.content], {
                            type: getMimeType(extension) + ';charset=utf-8'
                        });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = fileName;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                    }

                    // 保存执行数据
                    toolExecutions[actionId] = {
                        action: data.action,
                        input: data.input,
                        status: 'running',
                        startTime: (data.timestamp * 1000) || Date.now(),
                        progress: null,
                        result: null,
                        endTime: null
                    };

                    // 创建action group容器
                    // const actionGroup = document.createElement('div');
                    // actionGroup.className = 'action-group';
                    // actionGroup.setAttribute('data-action-id', actionId);
                    // answerElement.appendChild(actionGroup);
                    // currentActionGroup = actionGroup;

                    // 创建工具条目
                    const toolItem = document.createElement('div');
                    toolItem.className = 'tool-item';
                    toolItem.setAttribute('data-action-id', actionId);
                    toolItem.innerHTML = `
                        <span class="tool-name">${data.action}</span>
                        <span class="tool-status running">执行中 (0%)</span>
                        <button class="view-details-btn">
                            <span class="btn-text">查看详情</span>
                            ${Icons.detail}
                        </button>
                    `;

                    // 添加到工具列表
                    const toolsList = document.querySelector('.tools-list');
                    toolsList.appendChild(toolItem);

                    // 更新工具计数
                    const toolsCount = document.querySelector('.tools-count');
                    toolsCount.textContent = toolsList.children.length;

                    // 添加点击事件
                    toolItem.querySelector('.view-details-btn').addEventListener('click', (e) => {
                        e.stopPropagation();
                        const detailsContainer = document.querySelector('.tool-details-container');
                        detailsContainer.classList.add('visible');

                        const detailsContent = document.querySelector('.tool-details-content');
                        const execution = toolExecutions[actionId];

                        // 实时构建详情内容
                        let resultContent = '执行中...';
                        let metricsContent = `
                            <div class="metric">
                                <span class="metric-label">开始时间:</span>
                                <span class="metric-value">${new Date(execution.startTime).toLocaleTimeString()}</span>
                            </div>
                        `;

                        if (execution.status === 'completed') {
                            resultContent = `<pre>${typeof execution.result === 'string' ?
                                execution.result : JSON.stringify(execution.result, null, 2)}</pre>`;
                            metricsContent += `
                                <div class="metric">
                                    <span class="metric-label">结束时间:</span>
                                    <span class="metric-value">${new Date(execution.endTime).toLocaleTimeString()}</span>
                                </div>
                                <div class="metric">
                                    <span class="metric-label">执行耗时:</span>
                                    <span class="metric-value">${(execution.duration).toFixed(2)}ms</span>
                                </div>
                            `;
                        } else {
                            metricsContent += `
                                <div class="metric">
                                    <span class="metric-label">已执行:</span>
                                    <span class="metric-value">${Date.now() - execution.startTime}ms</span>
                                </div>
                            `;
                        }

                        detailsContent.innerHTML = `
                            <div class="tool-params-section">
                                <div class="tool-param">
                                    <div class="tool-param-label">工具名称</div>
                                    <div class="tool-param-value">${execution.action}</div>
                                </div>
                                <div class="tool-param">
                                    <div class="tool-param-label">参数</div>
                                    <div class="tool-param-value"><pre>${JSON.stringify(execution.input, null, 2)}</pre></div>
                                </div>
                            </div>
                            <div class="tool-result-section">
                                <div class="tool-result">
                                    <div class="result-label">执行结果</div>
                                    <div class="result-value">
                                        ${resultContent}
                                    </div>
                                </div>
                                <div class="tool-metrics">
                                    ${metricsContent}
                                </div>
                            </div>
                        `;

                        // 关闭按钮事件
                        detailsContainer.querySelector('.close-details').addEventListener('click', () => {
                            detailsContainer.classList.remove('visible');
                        });
                    });
                } catch (error) {
                    console.error('解析action开始事件失败:', error);
                }
            });

            // 处理工具进度事件
            eventSource.addEventListener('tool_progress', event => {
                try {
                    const data = JSON.parse(event.data);
                    const actionId = data.action_id || currentActionId;
                    if (!actionId) {
                        console.error('缺少action_id，且没有当前action_id');
                        return;
                    }

                    // 更新执行数据
                    if (toolExecutions[actionId]) {
                        toolExecutions[actionId].progress = data.progress;
                        currentActionId = actionId; // 更新当前actionId
                    }

                    // 更新工具状态
                    const toolItem = document.querySelector(`.tool-item[data-action-id="${actionId}"]`);
                    const actionGroup = document.querySelector(`.action-group[data-action-id="${actionId}"]`);

                    if (toolItem) {
                        const statusEl = toolItem.querySelector('.tool-status');
                        if (statusEl) {
                            statusEl.textContent = `执行中 (${data.progress || 0}%)`;
                            statusEl.className = 'tool-status running';
                        }
                    }

                    if (actionGroup) {
                        const statusEl = actionGroup.querySelector('.tool-status');
                        if (statusEl) {
                            statusEl.textContent = `执行中 (${data.progress || 0}%)`;
                        }
                    }

                    // 同时更新详情面板状态
                    const detailsContainer = document.querySelector('.tool-details-container.visible');
                    if (detailsContainer && detailsContainer.querySelector(`[data-action-id="${actionId}"]`)) {
                        const detailsContent = document.querySelector('.tool-details-content');
                        if (detailsContent) {
                            const resultValue = detailsContent.querySelector('.result-value');
                            if (resultValue) {
                                resultValue.textContent = `执行中... (${data.progress || 0}%)`;
                            }
                        }
                    }
                } catch (error) {
                    console.error('解析工具进度失败:', error);
                }
            });

            // 处理action完成事件
            eventSource.addEventListener('action_complete', event => {
                const timestamp = new Date().getTime(); // 使用当前时间作为fallback
                try {
                    const data = JSON.parse(event.data);
                    const actionId = data.action_id || currentActionId;
                    if (!actionId) {
                        console.error('缺少action_id，且没有当前action_id');
                        return;
                    }

                    // 更新执行数据
                    if (toolExecutions[actionId]) {
                        toolExecutions[actionId].status = 'completed';
                        toolExecutions[actionId].result = data.result;
                        toolExecutions[actionId].endTime = (data.timestamp * 1000) || Date.now(); // 秒转毫秒
                        toolExecutions[actionId].duration = toolExecutions[actionId].endTime - toolExecutions[actionId].startTime;
                        currentActionId = actionId; // 更新当前actionId
                    }

                    // 更新所有相关UI元素
                    const toolItem = document.querySelector(`.tool-item[data-action-id="${actionId}"]`);
                    const actionGroup = document.querySelector(`.action-group[data-action-id="${actionId}"]`);

                    if (toolItem) {
                        // 更新工具条目状态
                        const statusEl = toolItem.querySelector('.tool-status');
                        if (statusEl) {
                            statusEl.textContent = '完成';
                            statusEl.className = 'tool-status success';
                        }
                    }

                    if (actionGroup) {
                        // 更新action group状态
                        const statusEl = actionGroup.querySelector('.tool-status');
                        if (statusEl) {
                            statusEl.textContent = '完成';
                            statusEl.className = 'tool-status success';
                        }

                        // 添加执行结果
                        const detailsEl = actionGroup.querySelector('.tool-details');
                        if (detailsEl) {
                            detailsEl.innerHTML = `
                                <div class="tool-result">
                                    <pre>${typeof data.result === 'string' ?
                                    data.result : JSON.stringify(data.result, null, 2)}</pre>
                                </div>
                                <div class="tool-metrics">
                                    <div>执行时间: ${toolExecutions[actionId]?.duration || 0}ms</div>
                                </div>
                            `;
                        }
                    }

                    // 确保详情面板可见时更新内容
                    const visibleDetails = document.querySelector('.tool-details-container.visible');
                    if (visibleDetails && visibleDetails.querySelector(`[data-action-id="${actionId}"]`)) {
                        const detailsContent = document.querySelector('.tool-details-content');
                        if (detailsContent) {
                            const resultValue = detailsContent.querySelector('.result-value');
                            if (resultValue) {
                                resultValue.innerHTML = `<pre>${typeof data.result === 'string' ?
                                    data.result : JSON.stringify(data.result, null, 2)}</pre>`;
                            }
                        }
                    }
                } catch (error) {
                    console.error('解析action完成事件失败:', error);
                }
            });

            // 关闭详情面板事件
            document.querySelector('.close-details').addEventListener('click', () => {
                document.querySelector('.tool-details-container').classList.remove('visible');
            });

            // 处理agent开始事件
            // eventSource.addEventListener('agent_start', event => {
            //     try {
            //         const data = JSON.parse(event.data);
            //         const startDiv = document.createElement('div');
            //         startDiv.className = 'agent-start';
            //         const query = data.query;
            //         startDiv.innerHTML = `
            //             <div class="agent-info">
            //                 <span class="agent-status">智能体开始处理您的问题</span>
            //                 <span class="agent-query"></span>
            //                 <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
            //             </div>
            //         `;
            //         answerElement.appendChild(startDiv);
            //     } catch (error) {
            //         console.error('解析agent开始事件失败:', error);
            //     }
            // });

            // 处理agent思考事件
            eventSource.addEventListener('agent_thinking', event => {
                // if (currentModel != null && currentModel == "deep-research") {
                //     return;
                // }
                try {
                    const data = JSON.parse(event.data);
                    const thinkingDiv = document.createElement('div');
                    thinkingDiv.className = 'agent-thinking';
                    thinkingDiv.innerHTML = `
                        <div class="thinking-info">
                            <span class="thinking-indicator"></span>
                            <span class="thinking-content">${data.thought}</span>
                            <span class="thinking-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    `;
                    answerElement.appendChild(thinkingDiv);
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
                            <span class="error-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    `;
                    answerElement.appendChild(errorDiv);
                } catch (error) {
                    console.error('解析agent错误事件失败:', error);
                }
            });

            // 处理智能体评估事件
            eventSource.addEventListener('agent_evaluation', event => {
                try {
                    const data = JSON.parse(event.data);
                    const evaluationDiv = document.createElement('div');
                    evaluationDiv.className = 'agent-event agent-evaluation';

                    let satisfactionIcon = data.evaluation_result.is_satisfied ? '✓' : '✗';
                    let satisfactionClass = data.evaluation_result.is_satisfied ? 'satisfied' : 'unsatisfied';

                    evaluationDiv.innerHTML = `
                        <div class="agent-event-card">
                            <div class="agent-header">
                                <div class="agent-icon">🔍</div>
                                <div class="agent-meta">
                                    <span class="agent-name">${data.agent_name}</span>
                                    <div class="agent-status ${satisfactionClass}">
                                        <span class="status-icon">${satisfactionIcon}</span>
                                        <span>${data.evaluation_result.is_satisfied ? '满意' : '不满意'}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="agent-content">
                                <div class="agent-section">
                                    <div class="agent-detail">
                                        <span class="detail-label">评估结果:</span>
                                        <span class="detail-value">${data.evaluation_result.reason}</span>
                                    </div>
                                    ${data.evaluation_result.need_handover ? `
                                    <div class="agent-detail">
                                        <span class="detail-label">交接建议:</span>
                                        <span class="detail-value">${data.evaluation_result.handover_suggestions}</span>
                                    </div>
                                    ` : ''}
                                    ${data.feedback ? `
                                    <div class="agent-detail">
                                        <span class="detail-label">反馈:</span>
                                        <span class="detail-value">${data.feedback}</span>
                                    </div>
                                    ` : ''}
                                </div>
                                <div class="agent-footer">
                                    <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                                </div>
                            </div>
                        </div>
                    `;
                    answerElement.appendChild(evaluationDiv);
                } catch (error) {
                    console.error('解析智能体评估事件失败:', error);
                }
            });

            // 处理agent完成事件
            eventSource.addEventListener('agent_complete', event => {
                try {
                    const data = JSON.parse(event.data);
                    const content = data.result;
                    const completeDiv = document.createElement('div');
                    completeDiv.className = 'agent-complete';
                    completeDiv.innerHTML = `
                        <div class="complete-info">
                            <div class="action_complete">${marked.parse(content)}</div>
                        </div>
                    `;
                    answerElement.appendChild(completeDiv);
                } catch (error) {
                    console.error('解析agent完成事件失败:', error);
                }
            });

            // 处理完成事件
            eventSource.addEventListener('complete', event => {
                // try {
                //     const result = event.data;
                //     const message = result || '完成';
                //     const completeDiv = document.createElement('div');
                //     completeDiv.className = 'complete';
                //     completeDiv.innerHTML = `<div>${message}</div>`;
                //     answerElement.appendChild(completeDiv);
                // } catch (error) {
                //     const errorDiv = document.createElement('div');
                //     errorDiv.className = 'error';
                //     errorDiv.textContent = '解析完成事件失败';
                //     answerElement.appendChild(errorDiv);
                // }
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
});