import Icons from './icons.js';
import { generateConversationId, sanitizeFilename, getMimeType, downloadFileFromContent, fetchJSON } from './utils.js';
import { scrollToBottom as uiScrollToBottom, resetUI as uiResetUI, renderNodeResult as uiRenderNodeResult, renderExplanation as uiRenderExplanation, renderAnswer as uiRenderAnswer, createQuestionElement } from './ui.js';
import { registerSSEHandlers } from './sse-handlers.js';


// 临时存储历史对话数据 {model: htmlContent}
const historyStorage = {};
// 存储每个模型的conversation_id {model: conversationId}
const conversationIdStorage = {};
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
let currentConversationId = null; // 当前会话的conversation_id
const showIterationModels = ["super-agent", "home", "mcp-agent", "multi-agent", "browser-agent", "deep-research", "codeact-agent"];
// 提交用户输入的全局函数
async function submitUserInput(nodeId, inputType, prompt, agentId = undefined) {
    const inputField = document.getElementById(`user-input-${nodeId}`);
    if (!inputField) return;

    // 尝试获取同层的 submit 按钮（用于读取 data-agent-id 作为回退）
    let submitButton = inputField.parentElement ? inputField.parentElement.querySelector('.submit-input') : null;

    let value = inputField.value;
    if (!currentChatId) {
        console.error('No chat ID available');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = '提交失败: 无法获取会话ID';
        inputField.parentElement.appendChild(errorDiv);
        return;
    }

    // 辅助：构建要发送的 payload（会在发送处使用）
    const buildPayload = (node_id, val) => {
        const payload = {
            node_id,
            value: val,
            chat_id: currentChatId
        };
        // 优先使用显式传入的 agentId，其次尝试从 inputField 的 dataset 中读取，再尝试 submitButton 的 dataset
        // 注意：显式传入的 agentId 可能为 '' 或 0 等，只有当其不为 null/undefined 时视为有效（以避免无意忽略显式值）
        if (agentId !== undefined && agentId !== null) {
            payload.agent_id = agentId;
        } else if (inputField && inputField.dataset && inputField.dataset.agentId) {
            payload.agent_id = inputField.dataset.agentId;
        } else if (submitButton && submitButton.dataset && submitButton.dataset.agentId) {
            payload.agent_id = submitButton.dataset.agentId;
        }
        return payload;
    };

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
                    // 发送结果到后端（包含 agent_id 如果可用）
                    fetch('/user_input', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(buildPayload(nodeId, browser_result['result']))
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
                                    const submitButtonEl = container.nextElementSibling;
                                    if (submitButtonEl) {
                                        submitButtonEl.remove();
                                    }
                                }
                            }

                            // 自动发送位置数据到后端（包含 agent_id 如果可用）
                            fetch('/user_input', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify(buildPayload(nodeId, locationData))
                            }).then(response => {
                                if (!response.ok) {
                                    throw new Error('提交失败');
                                }
                                // 提交成功后禁用输入框和提交按钮
                                inputField.disabled = true;
                                const submitBtn = inputField.parentElement.querySelector('.submit-input');
                                if (submitBtn) {
                                    submitBtn.disabled = true;
                                    submitBtn.classList.add('submitted');
                                    submitBtn.textContent = '已提交';
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
            default:
                break;
        }

        // 发送用户输入到后端（包含 agent_id 如果可用）
        fetch('/user_input', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(buildPayload(nodeId, value))
        }).then(response => {
            if (!response.ok) {
                throw new Error('提交失败');
            }
            // 提交成功后禁用输入框和提交按钮
            inputField.disabled = true;
            const submitBtn = inputField.parentElement.querySelector('.submit-input');
            if (submitBtn) {
                submitBtn.disabled = true;
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

document.addEventListener('click', function (e) {
    const copyBtn = e.target.closest('.copy-btn');
    if (copyBtn) {
        // 找到最接近的容器
        const container = copyBtn.closest('.question') || copyBtn.closest('.action-group-item-details');

        let textToCopy = '';
        if (container) {
            // 如果是问题，复制其内部的文本内容（不包含复制按钮本身）
            if (container.classList.contains('question')) {
                // 复制原始的用户输入文本，而不是渲染后的HTML
                const questionTextElement = container.querySelector('.question-text'); // 假设问题文本在一个特定的元素中
                textToCopy = questionTextElement ? questionTextElement.textContent.trim() : '';
            } else if (container.classList.contains('action-group-item-details')) {
                // 如果是工具执行结果，复制 pre 标签内的文本
                const preElement = container.querySelector('pre');
                textToCopy = preElement ? preElement.textContent.trim() : '';
            }
        }

        if (!textToCopy) return;

        navigator.clipboard.writeText(textToCopy).then(() => {
            const tooltip = copyBtn.querySelector('.copy-tooltip');
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
    const modelSelect = document.getElementById('model-select');

    // 将左侧菜单项填充到聊天框左下角的下拉选择中（并保持与菜单互通）
    if (modelSelect) {
        modelOptions.forEach(item => {
            const model = item.getAttribute('data-model');
            const textDiv = item.querySelector('.menu-item-text');
            const label = textDiv ? textDiv.textContent.trim() : model;
            const opt = document.createElement('option');
            opt.value = model;
            opt.textContent = label;
            modelSelect.appendChild(opt);
        });

        // 当下拉变化时，触发对应菜单项的点击逻辑（复用现有处理）
        modelSelect.addEventListener('change', () => {
            const newModel = modelSelect.value;
            const target = Array.from(modelOptions).find(i => i.getAttribute('data-model') === newModel);
            if (target) {
                // 触发菜单项的点击逻辑（会做历史保存/恢复等）
                target.click();
            }
        });
    }

    // 填充具体模型名称下拉（从后端 /models 获取）
    const modelNameSelect = document.getElementById('model-name-select');
    if (modelNameSelect) {
        // 清理默认项，保留空选项
        // 从后端加载
        fetch('/models').then(resp => {
            if (!resp.ok) throw new Error('Failed to load models');
            return resp.json();
        }).then(data => {
            if (data && Array.isArray(data.models) && data.models.length > 0) {
                // 将每个模型加入下拉
                data.models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m;
                    modelNameSelect.appendChild(opt);
                });
                // 优化：默认选中第一个具体模型（跳过占位的空选项）
                // 如果页面中已有占位 option (value === '')，则选择第一个模型项；否则选择第一个 option
                const firstModelValue = data.models[0];
                try {
                    modelNameSelect.value = firstModelValue;
                    // 如果直接设置 value 无效（例如 option 尚未附着），则使用 selectedIndex 作为回退
                    if (modelNameSelect.value !== firstModelValue) {
                        // 寻找第一个非空值的 option 索引
                        const idx = Array.from(modelNameSelect.options).findIndex(o => o.value && o.value !== '');
                        if (idx >= 0) modelNameSelect.selectedIndex = idx;
                    }
                } catch (e) {
                    // 忽略错误，保留下拉现状并在控制台记录
                    console.warn('设置默认模型失败，保留占位项', e);
                }
            } else if (data && Array.isArray(data.models)) {
                // 空数组或其它情况，仍将（可能为空的）models 列表加入
                data.models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m;
                    modelNameSelect.appendChild(opt);
                });
            }
        }).catch(err => {
            console.error('加载模型列表失败:', err);
        });
    }

    // Thought 开关：读取本地存储并绑定切换事件（默认不展示）
    const thoughtToggle = document.getElementById('thought-toggle');
    try {
        const savedThought = localStorage.getItem('showThought');
        if (savedThought === 'true') {
            document.body.classList.add('show-thought');
            if (thoughtToggle) thoughtToggle.checked = true;
        } else {
            document.body.classList.remove('show-thought');
            if (thoughtToggle) thoughtToggle.checked = false;
        }
    } catch (e) {
        console.warn('读取 showThought 本地存储失败', e);
    }

    if (thoughtToggle) {
        thoughtToggle.addEventListener('change', function () {
            try {
                if (this.checked) {
                    // 选中：设置 class 并保存状态
                    document.body.classList.add('show-thought');
                    localStorage.setItem('showThought', 'true');
                } else {
                    // 取消选中：移除 class、清理页面中所有 .thought 元素 并保存状态
                    document.body.classList.remove('show-thought');
                    localStorage.setItem('showThought', 'false');

                    try {
                        // 移除所有已渲染的 thought 节点，避免保留空占位
                        document.querySelectorAll('.thought').forEach(el => el.remove());
                    } catch (cleanErr) {
                        console.warn('移除 .thought 元素失败', cleanErr);
                    }
                }
            } catch (e) {
                console.warn('设置 showThought 本地存储失败', e);
            }
        });
    }

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
            // 为初始模型生成conversation_id
            currentConversationId = generateConversationId();
            conversationIdStorage[currentModel] = currentConversationId;
            // 同步下拉选中
            if (modelSelect) modelSelect.value = currentModel;
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

            // 1. 存储当前对话历史
            const conversationHistory = document.getElementById('conversation-history');
            if (currentModel && conversationHistory.children.length > 0) {
                historyStorage[currentModel] = conversationHistory.innerHTML;
            }

            // 2. 存储当前模型的conversation_id
            if (currentModel && currentConversationId) {
                conversationIdStorage[currentModel] = currentConversationId;
            }

            // 3. 清空当前对话历史
            conversationHistory.innerHTML = '';

            // 4. 恢复新模型的对话历史(如果存在)
            if (historyStorage[newModel]) {
                conversationHistory.innerHTML = historyStorage[newModel];
            }

            // 5. 恢复或生成新模型的conversation_id
            if (conversationIdStorage[newModel]) {
                currentConversationId = conversationIdStorage[newModel];
            } else {
                // 为新模型生成新的conversation_id
                currentConversationId = generateConversationId();
                conversationIdStorage[newModel] = currentConversationId;
            }

            // 更新UI状态
            document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
            this.classList.add('active');
            currentModel = newModel;
            updateIterationDisplay(this);
            // 同步下拉选择（如果存在）
            if (modelSelect) {
                modelSelect.value = newModel;
            }
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
        sanitize: false,     // 这里仍让 marked 输出 HTML，由我们在渲染前进行安全过滤
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

    // 简单安全清理：移除 <script> 和 <style>，并删除所有 on* 事件属性与 javascript: 协议的 href/src
    function sanitizeHTML(html) {
        const template = document.createElement('template');
        template.innerHTML = html;
        const treeWalker = document.createTreeWalker(template.content, NodeFilter.SHOW_ELEMENT, null, false);
        const toRemove = [];
        while (treeWalker.nextNode()) {
            const el = treeWalker.currentNode;
            const tag = el.tagName && el.tagName.toLowerCase();
            if (tag === 'script' || tag === 'style') {
                toRemove.push(el);
                continue;
            }
            // 删除事件处理器属性和危险属性值
            Array.from(el.attributes).forEach(attr => {
                const name = attr.name.toLowerCase();
                const val = (attr.value || '').toLowerCase();
                if (name.startsWith('on')) {
                    el.removeAttribute(attr.name);
                } else if ((name === 'href' || name === 'src' || name === 'xlink:href') && val.startsWith('javascript:')) {
                    el.removeAttribute(attr.name);
                } else if (name === 'style') {
                    // 可根据需要对 style 做更严格白名单，这里简单移除内联 style 以减少风险
                    el.removeAttribute('style');
                }
            });
        }
        toRemove.forEach(n => n.remove());
        return template.innerHTML;
    }

    // 将 Markdown 渲染为 HTML 并通过 sanitizeHTML 过滤后返回安全的 HTML
    function renderMarkdownSafe(mdText) {
        try {
            const raw = marked.parse(mdText || '');
            return sanitizeHTML(raw);
        } catch (e) {
            console.warn('Markdown 渲染失败，回退为纯文本显示', e);
            const esc = (mdText || '').replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>');
            return `<pre>${esc}</pre>`;
        }
    }

    // wrapper -> 调用 ui 模块的 scrollToBottom，传入 conversationHistory
    function scrollToBottom() {
        if (typeof uiScrollToBottom === 'function') {
            try { uiScrollToBottom(conversationHistory); } catch (e) { console.warn('uiScrollToBottom 调用失败', e); }
        }
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

    // wrapper -> 调用 ui 模块的 resetUI，传入 userInput 和 sendButton
    function resetUI() {
        isProcessing = false;
        if (typeof uiResetUI === 'function') {
            try { uiResetUI(userInput, sendButton); } catch (e) { console.warn('uiResetUI 调用失败', e); }
        } else {
            userInput.value = '';
            userInput.disabled = false;
            sendButton.disabled = false;
            sendButton.textContent = '发送';
            sendButton.classList.remove('stop');
            userInput.focus();
        }
    }

    // wrapper -> 调用 ui 模块的 renderNodeResult，传入 currentIteration
    function renderNodeResult(data, container) {
        if (typeof uiRenderNodeResult === 'function') {
            try { uiRenderNodeResult(data, container, currentIteration); } catch (e) { console.warn('uiRenderNodeResult 调用失败', e); }
            return;
        }
        // fallback: minimal rendering if ui 模块不可用
        const el = document.createElement('div');
        el.className = 'node-result';
        el.textContent = `${data.node_id}: ${data.status || ''}`;
        container.appendChild(el);
    }

    // wrapper -> 调用 ui 模块的 renderExplanation
    function renderExplanation(content, container) {
        if (typeof uiRenderExplanation === 'function') {
            try { uiRenderExplanation(content, container); } catch (e) { console.warn('uiRenderExplanation 调用失败', e); }
            return;
        }
        const div = container.querySelector('.explanation') || (() => {
            const d = document.createElement('div'); d.className = 'explanation'; container.appendChild(d); return d;
        })();
        div.innerHTML = marked.parse(content);
    }

    // wrapper -> 调用 ui 模块的 renderAnswer
    function renderAnswer(content, container) {
        if (typeof uiRenderAnswer === 'function') {
            try { uiRenderAnswer(content, container); } catch (e) { console.warn('uiRenderAnswer 调用失败', e); }
            return;
        }
        let answerDiv = container.querySelector('.answer:last-child');
        if (!answerDiv) {
            answerDiv = document.createElement('div');
            answerDiv.className = 'answer';
            container.appendChild(answerDiv);
        }
        answerDiv.innerHTML = marked.parse(content);
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

        // 添加问题（使用 Markdown 渲染，且做安全过滤）
        const questionDiv = document.createElement('div');
        questionDiv.className = 'question';
        // 添加复制按钮到左侧
        const copyBtn = document.createElement('button'); // 使用 button 元素
        copyBtn.className = 'copy-btn small'; // 添加 small 类以匹配工具结果的复制按钮样式
        copyBtn.innerHTML = `
            <svg class="copy-icon" fill="currentColor" viewBox="0 0 20 20">
                <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z"></path>
                <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z"></path>
            </svg>
            <span class="copy-tooltip">复制</span>
        `;
        questionDiv.appendChild(copyBtn); // 将复制按钮添加到 questionDiv 内部

        // 添加问题文本（使用 Markdown 渲染，且做安全过滤）
        const questionTextDiv = document.createElement('div');
        questionTextDiv.className = 'question-text'; // 新增一个 div 来包裹问题文本
        questionTextDiv.innerHTML = renderMarkdownSafe(text);
        questionDiv.appendChild(questionTextDiv); // 将问题文本添加到 questionDiv 内部

        qaContainer.appendChild(questionDiv);

        // 添加回答容器
        const answerElement = document.createElement('div');
        answerElement.className = 'answer';
        qaContainer.appendChild(answerElement);

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

            // 统一读取具体模型下拉（如果存在），并规范化为空值为 undefined
            const selectedModelNameEl = document.getElementById('model-name-select');
            const rawSelectedModelName = selectedModelNameEl ? selectedModelNameEl.value : '';
            const selectedModelName = rawSelectedModelName && rawSelectedModelName.trim() !== '' ? rawSelectedModelName.trim() : undefined;

            let response;
            if (selectedModel === 'multi-agent') {
                // 多智能体模式使用 /agents/route 接口
                // 将 model_name 也一并传递，便于后端区分具体底层模型
                response = await fetch('/agents/route', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: text,
                        conversation_id: currentConversationId,
                        max_iterations: parseInt(document.getElementById('itecount').value) || 10,
                        stream: true,
                        model_name: selectedModelName
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
                        model_name: selectedModelName,
                        conversation_id: currentConversationId,
                        itecount: showIterationModels.includes(selectedModel) ? parseInt(document.getElementById('itecount').value) : undefined,
                        conversation_count: parseInt(document.getElementById('conversation_count').value) || 5
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

            // 将 SSE 事件处理委托到 sse-handlers 模块
            try {
                // 临时存储工具调用数据，因为工具详情将直接显示在聊天流中
                const toolExecutions = {};
                registerSSEHandlers(eventSource, {
                    answerElement: answerElement,
                    toolExecutions: toolExecutions,
                    currentActionIdRef: { value: currentActionId },
                    currentIterationRef: { value: currentIteration },
                    renderNodeResult: renderNodeResult,
                    renderExplanation: renderExplanation,
                    renderAnswer: renderAnswer,
                    createQuestionElement: createQuestionElement,
                    Icons: Icons,
                    submitUserInput: submitUserInput,
                    onComplete: () => { resetUI(); },
                    onError: () => { /* 全局错误处理（保留空实现） */ }
                });
            } catch (e) {
                console.warn('registerSSEHandlers 调用失败', e);
            }

        } catch (error) {
            console.error('发送消息失败:', error);
            answerElement.innerHTML += `<div class="error">发送消息失败: ${error.message}</div>`;
            resetUI();
        }
    }
});