import Icons from './icons.js';
import { generateConversationId, sanitizeFilename, getMimeType, downloadFileFromContent, fetchJSON } from './utils.js';
import { scrollToBottom as uiScrollToBottom, resetUI as uiResetUI, renderNodeResult as uiRenderNodeResult, renderExplanation as uiRenderExplanation, renderAnswer as uiRenderAnswer, createQuestionElement, streamTextContent as uiStreamTextContent, updatePlaybook as uiUpdatePlaybook } from './ui.js';
import { registerSSEHandlers } from './sse-handlers.js';

// 保存到知识库的函数
async function saveToKnowledgeBase(question, answer) {
    try {
        const response = await fetch('/knowledge_base/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: `${answer}`
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        if (result.success) {
            alert('内容已成功保存到知识库！');
            console.log('保存到知识库成功:', result);
        } else {
            alert('保存到知识库失败: ' + (result.message || '未知错误'));
            console.error('保存到知识库失败:', result);
        }
    } catch (error) {
        alert('保存到知识库失败，请查看控制台了解详情。');
        console.error('保存到知识库异常:', error);
    }
}

// 辅助函数:渲染数学表达式
function renderMathInElement(element) {
    if (typeof window.renderMathInElement !== 'undefined' && typeof katex !== 'undefined') {
        try {
            // 使用 KaTeX 的 auto-render 扩展来渲染数学表达式
            window.renderMathInElement(element, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\[', right: '\\]', display: true },
                    { left: '\\(', right: '\\)', display: false }
                ],
                throwOnError: false,
                errorColor: '#cc0000',
                strict: false,
                trust: true
            });
        } catch (e) {
            console.warn('KaTeX 渲染失败:', e);
        }
    }
}

// 这些辅助函数已不再需要,因为只在最终结果中使用数学表达式渲染
// 所有其他地方直接使用 marked.parse()


// 临时存储历史对话数据 {model: htmlContent}
const historyStorage = {};
// 存储每个模型的playbook数据 {model: playbookContent}
const playbookStorage = {};
// 存储每个模型的conversation_id {model: conversationId}
const conversationIdStorage = {};
// 异步获取 playbook 内容的函数
async function fetchPlaybook() {
    if (!currentConversationId) {
        console.warn('无法获取 playbook: currentConversationId 为空');
        return null;
    }
    try {
        const response = await fetch(`/playbook/${currentChatId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.success && data.playbook && data.playbook.tasks_and_completion) {
            // 将任务列表转换为 Markdown 格式
            return data.playbook.tasks_and_completion.join('\n');
        }
        return null;
    } catch (error) {
        console.error('获取 playbook 失败:', error);
        return null;
    }
}
// 侧边栏拖拽功能
document.addEventListener('DOMContentLoaded', function () {
    // 添加菜单项点击事件
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function () {
            document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // 侧边栏拖拽功能
    function initSidebarResizer() {
        const leftSidebar = document.getElementById('leftSidebar');
        const rightSidebar = document.getElementById('rightSidebar');
        const leftResizer = document.getElementById('leftResizer');
        const rightResizer = document.getElementById('rightResizer');
        const mainContainer = document.querySelector('.main-container');

        if (!leftSidebar || !rightSidebar || !leftResizer || !rightResizer || !mainContainer) {
            console.warn('侧边栏拖拽元素未找到，跳过初始化');
            return;
        }

        // 左侧拖拽功能
        let isLeftDragging = false;
        let startXLeft = 0;
        let startWidthLeft = 0;

        leftResizer.addEventListener('mousedown', function (e) {
            isLeftDragging = true;
            startXLeft = e.clientX;
            startWidthLeft = parseInt(document.defaultView.getComputedStyle(leftSidebar).width, 10);

            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            leftResizer.classList.add('dragging');

            e.preventDefault();
        });

        // 右侧拖拽功能
        let isRightDragging = false;
        let startXRight = 0;
        let startWidthRight = 0;

        rightResizer.addEventListener('mousedown', function (e) {
            isRightDragging = true;
            startXRight = e.clientX;
            startWidthRight = parseInt(document.defaultView.getComputedStyle(rightSidebar).width, 10);

            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            rightResizer.classList.add('dragging');

            e.preventDefault();
        });

        // 鼠标移动事件
        document.addEventListener('mousemove', function (e) {
            if (isLeftDragging) {
                const deltaX = e.clientX - startXLeft;
                const newWidth = Math.max(200, Math.min(500, startWidthLeft + deltaX));

                leftSidebar.style.width = `${newWidth}px`;
                // 更新左侧分隔线位置
                leftResizer.style.left = `calc(${newWidth}px - 4px)`;
                // 更新CSS变量，确保其他样式也能响应
                document.documentElement.style.setProperty('--sidebar-width', `${newWidth}px`);
            }

            if (isRightDragging) {
                const deltaX = startXRight - e.clientX;
                const newWidth = Math.max(200, Math.min(500, startWidthRight + deltaX));

                rightSidebar.style.width = `${newWidth}px`;
                // 更新右侧分隔线位置
                rightResizer.style.right = `calc(${newWidth}px - 4px)`;
                // 更新CSS变量，确保其他样式也能响应
                document.documentElement.style.setProperty('--sidebar-width', `${newWidth}px`);
            }
        });

        // 鼠标释放事件
        document.addEventListener('mouseup', function () {
            if (isLeftDragging || isRightDragging) {
                isLeftDragging = false;
                isRightDragging = false;

                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                leftResizer.classList.remove('dragging');
                rightResizer.classList.remove('dragging');
            }
        });

        // 防止拖拽时选中文本
        document.addEventListener('selectstart', function (e) {
            if (isLeftDragging || isRightDragging) {
                e.preventDefault();
            }
        });
    }

    // 初始化侧边栏拖拽功能
    initSidebarResizer();
});


// 存储当前chat_id和处理状态的全局变量
let currentChatId = null;
let isProcessing = false;
let currentModel = null; // 当前选择的菜单模式
let currentConversationId = null; // 当前会话的conversation_id
const showIterationModels = ["chat", "super-agent", "mcp-agent", "browser-agent", "deep-research", "deep-research-multi", "codeact-agent"];

// 会话列表延迟更新机制
let conversationListUpdateTimer = null; // 延迟更新定时器
const CONVERSATION_LIST_UPDATE_DELAY = 8000; // 8秒延迟

// 会话级“工具洞察”开关读取（仅以当前会话为准）
// 说明：避免被历史 localStorage 的 options_memory_enabled 干扰
function isToolInsightEnabled() {
    try {
        return sessionStorage.getItem('tool_insight_enabled') === 'true';
    } catch (e) {
        return false;
    }
}

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

// marked 库的配置
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
        // 对于 Mermaid 代码块，不进行语法高亮
        if (lang === 'mermaid') {
            return code;
        }
        try {
            return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
        } catch (e) {
            return hljs.highlightAuto(code).value;
        }
    },
    baseUrl: null,
    listItemIndent: '1' // 规范列表缩进
});

// 自定义 marked 渲染器以支持 Mermaid
if (typeof marked !== 'undefined') {
    const renderer = new marked.Renderer();
    const originalCodeRenderer = renderer.code.bind(renderer);

    renderer.code = function (code, language) {
        if (language === 'mermaid') {
            // 为 Mermaid 代码块创建特殊容器
            return `<div class="mermaid">${code}</div>`;
        }
        return originalCodeRenderer(code, language);
    };

    marked.use({ renderer });
}

// 初始化 Mermaid（如果可用）
if (typeof mermaid !== 'undefined') {
    mermaid.initialize({
        startOnLoad: true,
        theme: 'default',
        securityLevel: 'loose',
        fontFamily: 'Arial, sans-serif'
    });
}

// 显示文件解析结果的弹框
function showFileAnalysisModal(filename, content, fileType) {
    const modal = document.getElementById('toolResultModal');
    const modalTitle = modal.querySelector('.modal-title');
    const modalBody = modal.querySelector('.modal-result-content');
    const closeModalBtn = modal.querySelector('.close-modal-btn');

    modalTitle.textContent = `文件解析结果: ${filename} (${fileType})`;
    modalBody.innerHTML = renderMarkdownSafe(content); // 使用现有的 Markdown 渲染函数

    modal.style.display = 'block'; // 显示弹框

    // 关闭弹框事件
    closeModalBtn.onclick = function () {
        modal.style.display = 'none';
    };

    // 点击弹框外部关闭
    window.onclick = function (event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    };
}

// 存储已上传文件的全局数组
const uploadedFiles = [];

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

// 会话列表相关函数
/**
 * 启动延迟更新会话列表
 * 如果已有定时器在运行，则清除旧定时器，重新计时
 * 确保只在最后一次调用后的8秒执行一次更新
 */
function scheduleConversationListUpdate() {
    // 清除之前的定时器（如果存在）
    if (conversationListUpdateTimer) {
        clearTimeout(conversationListUpdateTimer);
        conversationListUpdateTimer = null;
    }

    // 设置新的延迟更新定时器
    conversationListUpdateTimer = setTimeout(() => {
        loadConversationList();
        conversationListUpdateTimer = null;
        console.log('延迟更新会话列表已执行');
    }, CONVERSATION_LIST_UPDATE_DELAY);

    console.log('已启动会话列表延迟更新，将在8秒后执行');
}

async function loadConversationList() {
    const conversationList = document.getElementById('conversation-list');
    if (!conversationList) return;

    try {
        const response = await fetch('/conversations?limit=50');
        const data = await response.json();

        if (data.success && data.conversations && data.conversations.length > 0) {
            conversationList.innerHTML = '';
            data.conversations.forEach(conv => {
                const convItem = document.createElement('div');
                convItem.className = 'conversation-item';
                convItem.dataset.conversationId = conv.conversation_id;

                const convTitle = document.createElement('div');
                convTitle.className = 'conversation-title';
                convTitle.textContent = conv.title || '未命名会话';
                convTitle.title = conv.initial_question || '';

                const convMeta = document.createElement('div');
                convMeta.className = 'conversation-meta';
                const createdDate = new Date(conv.updated_at);

                // 判断是否为当天
                const now = new Date();
                const isToday = createdDate.getFullYear() === now.getFullYear() &&
                    createdDate.getMonth() === now.getMonth() &&
                    createdDate.getDate() === now.getDate();

                // 当天显示时分秒，非当天显示日期
                const timeStr = isToday
                    ? createdDate.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                    : createdDate.toLocaleDateString('zh-CN');

                convMeta.textContent = `${timeStr} · ${conv.chat_count || 0} 条消息`;

                // 创建按钮容器
                const buttonContainer = document.createElement('div');
                buttonContainer.className = 'conversation-buttons';

                // 编辑按钮
                const editBtn = document.createElement('button');
                editBtn.className = 'edit-conversation-btn';
                editBtn.innerHTML = '✏️';
                editBtn.title = '编辑标题';
                editBtn.onclick = (e) => {
                    e.stopPropagation();
                    enableTitleEditing(convTitle, conv.conversation_id);
                };

                // 删除按钮
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-conversation-btn';
                deleteBtn.innerHTML = '×';
                deleteBtn.title = '删除会话';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    showDeleteConfirmModal(conv.conversation_id, conv.title || '未命名会话');
                };

                buttonContainer.appendChild(editBtn);
                buttonContainer.appendChild(deleteBtn);

                convItem.appendChild(convTitle);
                convItem.appendChild(convMeta);
                convItem.appendChild(buttonContainer);

                // 添加点击事件，处理选中状态
                convItem.onclick = (e) => {
                    // 如果点击的是编辑或删除按钮，不处理选中状态
                    if (e.target.closest('.conversation-buttons')) {
                        return;
                    }
                    
                    // 移除所有其他会话项的选中状态
                    document.querySelectorAll('.conversation-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    
                    // 为当前点击的会话项添加选中状态
                    convItem.classList.add('active');
                    
                    // 加载会话内容
                    loadConversation(conv.conversation_id);
                };

                conversationList.appendChild(convItem);
            });
        } else {
            conversationList.innerHTML = '<div class="conversation-list-empty">暂无会话历史</div>';
        }
    } catch (error) {
        console.error('加载会话列表失败:', error);
        conversationList.innerHTML = '<div class="conversation-list-error">加载失败</div>';
    }
}

// 启用标题编辑功能
function enableTitleEditing(titleElement, conversationId) {
    const originalTitle = titleElement.textContent;
    
    // 创建输入框
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'conversation-title-edit';
    input.value = originalTitle;
    input.style.width = '100%';
    input.style.padding = '4px 8px';
    input.style.border = '1px solid #007bff';
    input.style.borderRadius = '4px';
    input.style.fontSize = 'inherit';
    input.style.fontFamily = 'inherit';
    input.style.background = 'white';
    input.style.color = 'inherit';
    
    // 替换标题为输入框
    titleElement.style.display = 'none';
    titleElement.parentNode.insertBefore(input, titleElement);
    
    // 自动聚焦并选中所有文本
    input.focus();
    input.select();
    
    // 处理回车提交
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            await submitTitleEdit(input, titleElement, conversationId);
        } else if (e.key === 'Escape') {
            // 取消编辑
            cancelTitleEdit(input, titleElement);
        }
    });
    
    // 处理失去焦点
    input.addEventListener('blur', async () => {
        await submitTitleEdit(input, titleElement, conversationId);
    });
}

// 提交标题编辑
async function submitTitleEdit(input, titleElement, conversationId) {
    const newTitle = input.value.trim();
    
    if (!newTitle) {
        // 如果标题为空，恢复原标题
        cancelTitleEdit(input, titleElement);
        return;
    }
    
    if (newTitle === titleElement.textContent) {
        // 标题没有变化，直接恢复
        cancelTitleEdit(input, titleElement);
        return;
    }
    
    try {
        // 发送更新请求
        const response = await fetch(`/conversations/${conversationId}/title`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ title: newTitle })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 更新成功
            titleElement.textContent = newTitle;
            titleElement.title = newTitle;
            input.remove();
            titleElement.style.display = '';
            
            // 显示成功提示
            showToast('标题已更新', 'success');
        } else {
            // 更新失败，恢复原标题
            showToast('更新失败: ' + (result.message || '未知错误'), 'error');
            cancelTitleEdit(input, titleElement);
        }
    } catch (error) {
        console.error('更新会话标题失败:', error);
        showToast('更新失败，请重试', 'error');
        cancelTitleEdit(input, titleElement);
    }
}

// 取消标题编辑
function cancelTitleEdit(input, titleElement) {
    input.remove();
    titleElement.style.display = '';
}

// 显示提示消息
function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast-message toast-${type}`;
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '4px';
    toast.style.color = 'white';
    toast.style.zIndex = '10000';
    toast.style.fontSize = '14px';
    toast.style.maxWidth = '300px';
    toast.style.wordBreak = 'break-word';
    
    // 设置背景色
    if (type === 'success') {
        toast.style.background = '#28a745';
    } else if (type === 'error') {
        toast.style.background = '#dc3545';
    } else {
        toast.style.background = '#17a2b8';
    }
    
    // 添加到页面
    document.body.appendChild(toast);
    
    // 3秒后自动移除
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 3000);
}

async function loadConversation(conversationId) {
    // 如果正在处理问题，不允许加载会话
    if (isProcessing) {
        console.warn('当前正在处理问题，无法加载会话');
        showErrorMessage('当前正在处理问题，请等待完成后再加载历史会话');
        return;
    }

    try {
        // 1. 获取会话详情，包含chat_ids列表
        const response = await fetch(`/conversations/${conversationId}`);
        const data = await response.json();

        if (!data.success || !data.conversation) {
            console.error('获取会话详情失败');
            return;
        }

        const conversation = data.conversation;
        const chatIds = conversation.chat_ids || [];

        if (chatIds.length === 0) {
            console.warn('该会话没有聊天记录');
            return;
        }

        // 2. 更新 conversationIdStorage
        const selectedModul = document.getElementById('model-select').value;
        conversationIdStorage[selectedModul] = conversationId;

        // 3. 清空当前对话历史
        const conversationHistory = document.getElementById('conversation-history');
        if (conversationHistory) {
            conversationHistory.innerHTML = '';
        }

        // 4. 清空右侧 playbook（使用 updatePlaybook 函数确保正确清空并隐藏容器）
        if (typeof uiUpdatePlaybook === 'function') {
            uiUpdatePlaybook([]);  // 传递空数组来清空 playbook
        } else {
            const playbookContent = document.getElementById('playbook-content');
            const playbookContainer = document.querySelector('.playbook-container');
            if (playbookContent) {
                playbookContent.innerHTML = '';
            }
            if (playbookContainer) {
                playbookContainer.classList.remove('is-visible');
            }
        }

        // 5. 遍历chat_ids，依次回放每个chat
        for (let i = 0; i < chatIds.length; i++) {
            const chatId = chatIds[i];
            console.log(`正在回放第 ${i + 1}/${chatIds.length} 个chat: ${chatId}`);

            // 为每个chat创建一个容器
            const chatContainer = document.createElement('div');
            chatContainer.className = 'history-item';
            chatContainer.setAttribute('data-chat-id', chatId);

            // 创建qa-container
            const qaContainer = document.createElement('div');
            qaContainer.className = 'qa-container';

            // 添加回答容器
            const answerElement = document.createElement('div');
            answerElement.className = 'answer';
            qaContainer.appendChild(answerElement);

            chatContainer.appendChild(qaContainer);
            conversationHistory.appendChild(chatContainer);

            // 等待回放完成
            await replayChat(chatId, answerElement);
        }

        console.log('会话回放完成:', conversationId);

    } catch (error) {
        console.error('加载会话失败:', error);
        alert('加载会话失败: ' + error.message);
    }
}

// 回放单个chat的函数
async function replayChat(chatId, answerElement) {
    return new Promise((resolve, reject) => {
        try {
            // 建立SSE连接到回放接口
            const eventSource = new EventSource(`/replay/stream/${chatId}`);

            // 注册SSE事件处理器
            const toolExecutions = {};
            const currentActionIdRef = { value: null };
            const currentIterationRef = { value: 1 };

            registerSSEHandlers(eventSource, {
                answerElement: answerElement,
                toolExecutions: toolExecutions,
                currentActionIdRef: currentActionIdRef,
                currentIterationRef: currentIterationRef,
                renderNodeResult: uiRenderNodeResult,
                renderExplanation: uiRenderExplanation,
                renderAnswer: uiRenderAnswer,
                createQuestionElement: createQuestionElement,
                Icons: Icons,
                submitUserInput: submitUserInput,
                streamTextContent: uiStreamTextContent,
                updatePlaybook: uiUpdatePlaybook,
                fetchPlaybook: fetchPlaybook,
                currentModel: currentModel,
                playbookStorage: playbookStorage,
                conversationIdStorage: conversationIdStorage,
                scheduleConversationListUpdate: scheduleConversationListUpdate,
                scrollToBottom: () => {
                    // 回放时的滚动函数
                    const conversationHistory = document.getElementById('conversation-history');
                    if (conversationHistory && typeof uiScrollToBottom === 'function') {
                        uiScrollToBottom(conversationHistory);
                    }
                },
                saveToKnowledgeBase: saveToKnowledgeBase, // 传递保存到知识库函数
                onComplete: () => {
                    console.log(`Chat ${chatId} 回放完成`);
                    resolve();
                },
                onError: () => {
                    console.error(`Chat ${chatId} 回放出错`);
                    reject(new Error(`Chat ${chatId} 回放失败`));
                }
            });

        } catch (error) {
            console.error(`回放chat ${chatId} 失败:`, error);
            reject(error);
        }
    });
}

// 显示删除确认模态框
function showDeleteConfirmModal(conversationId, conversationTitle) {
    const modal = document.getElementById('deleteConversationModal');
    const closeBtn = modal.querySelector('.close-modal-btn');
    const cancelBtn = modal.querySelector('.modal-btn-cancel');
    const confirmBtn = modal.querySelector('.modal-btn-confirm');
    const messageEl = modal.querySelector('.modal-message');

    // 更新消息内容
    messageEl.textContent = `确定要删除会话"${conversationTitle}"吗？此操作无法撤销。`;

    // 显示模态框
    modal.style.display = 'block';
    modal.classList.add('visible');

    // 关闭模态框的函数
    const closeModal = () => {
        modal.style.display = 'none';
        modal.classList.remove('visible');
        // 移除事件监听器
        closeBtn.onclick = null;
        cancelBtn.onclick = null;
        confirmBtn.onclick = null;
        window.onclick = null;
    };

    // 关闭按钮事件
    closeBtn.onclick = closeModal;

    // 取消按钮事件
    cancelBtn.onclick = closeModal;

    // 确认删除按钮事件
    confirmBtn.onclick = async () => {
        closeModal();
        await deleteConversation(conversationId);
    };

    // 点击模态框外部关闭
    window.onclick = (event) => {
        if (event.target === modal) {
            closeModal();
        }
    };
}

async function deleteConversation(conversationId) {
    try {
        const response = await fetch(`/conversations/${conversationId}`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (data.success) {
            // 重新加载会话列表
            await loadConversationList();
        } else {
            // 使用友好的错误提示
            showErrorMessage('删除失败: ' + (data.message || '未知错误'));
        }
    } catch (error) {
        console.error('删除会话失败:', error);
        showErrorMessage('删除失败，请稍后重试');
    }
}

// 显示错误消息（使用模态框）
function showErrorMessage(message) {
    const modal = document.getElementById('deleteConversationModal');
    const closeBtn = modal.querySelector('.close-modal-btn');
    const messageEl = modal.querySelector('.modal-message');
    const actionsDiv = modal.querySelector('.modal-actions');
    const titleEl = modal.querySelector('.modal-title');

    // 更新标题和消息
    titleEl.textContent = '错误';
    messageEl.textContent = message;

    // 隐藏操作按钮，只显示关闭按钮
    actionsDiv.style.display = 'none';

    // 显示模态框
    modal.style.display = 'block';
    modal.classList.add('visible');

    // 关闭模态框的函数
    const closeModal = () => {
        modal.style.display = 'none';
        modal.classList.remove('visible');
        // 恢复标题和操作按钮
        titleEl.textContent = '确认删除';
        actionsDiv.style.display = 'flex';
        closeBtn.onclick = null;
        window.onclick = null;
    };

    // 关闭按钮事件
    closeBtn.onclick = closeModal;

    // 点击模态框外部关闭
    window.onclick = (event) => {
        if (event.target === modal) {
            closeModal();
        }
    };
}

function createNewConversation() {
    // 清空对话历史
    const conversationHistory = document.getElementById('conversation-history');
    if (conversationHistory) {
        conversationHistory.innerHTML = '';
    }

    // 清空右侧 playbook 区域
    const playbookContent = document.getElementById('playbook-content');
    if (playbookContent) {
        playbookContent.innerHTML = '';
    }

    // 清空 playbookStorage 中当前模型的内容
    const selectedModul = document.getElementById('model-select').value;
    if (playbookStorage && selectedModul) {
        playbookStorage[selectedModul] = '';
    }

    // 生成新的 conversationId
    conversationIdStorage[selectedModul] = generateConversationId();

    // 清空输入框
    const userInput = document.getElementById('user-input');
    if (userInput) {
        userInput.value = '';
        userInput.focus();
    }

    // 重新加载会话列表
    loadConversationList();

    console.log('已创建新会话');
}

document.addEventListener('DOMContentLoaded', () => {
    // 初始化会话列表
    loadConversationList();

    // 新建会话按钮事件
    const newConversationBtn = document.getElementById('new-conversation-btn');
    if (newConversationBtn) {
        newConversationBtn.addEventListener('click', createNewConversation);
    }

    // 选项面板显示/隐藏逻辑
    const optionsButton = document.getElementById('options-button');
    const optionsPanel = document.getElementById('options-panel');
    const closeOptionsPanel = document.getElementById('close-options-panel');

    function toggleOptionsPanel() {
        if (optionsPanel.style.display === 'none' || !optionsPanel.style.display) {
            optionsPanel.style.display = 'block';
        } else {
            optionsPanel.style.display = 'none';
        }
    }

    function closeOptionsPanelHandler() {
        optionsPanel.style.display = 'none';
    }

    // 点击+号按钮切换面板
    if (optionsButton) {
        optionsButton.addEventListener('click', toggleOptionsPanel);
    }

    // 点击关闭按钮关闭面板
    if (closeOptionsPanel) {
        closeOptionsPanel.addEventListener('click', closeOptionsPanelHandler);
    }

    // 点击面板外部关闭面板
    document.addEventListener('click', (event) => {
        if (optionsPanel && optionsPanel.style.display === 'block') {
            const isClickInsideOptionsButton = optionsButton.contains(event.target);
            const isClickInsidePanel = optionsPanel.contains(event.target);

            if (!isClickInsideOptionsButton && !isClickInsidePanel) {
                closeOptionsPanelHandler();
            }
        }
    });

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

    // 限制“迭代轮次”和“会话轮次”为三位数字并缩窄输入框
    const itecountInput = document.getElementById('itecount');
    const conversationCountInput = document.getElementById('conversation_count');
    [itecountInput, conversationCountInput].forEach((inp) => {
        if (!inp) return;
        try {
            // 属性限制
            inp.setAttribute('max', '999');
            if (!inp.getAttribute('min')) inp.setAttribute('min', '1');
            inp.setAttribute('inputmode', 'numeric'); // 移动端数字键盘


            // 实时限制为最多三位纯数字
            inp.addEventListener('input', () => {
                let v = (inp.value || '').replace(/\D/g, '');
                if (v.length > 3) v = v.slice(0, 3);
                // 去掉前导零（但允许单个 0 被替换为 1 在 blur 时处理）
                v = v.replace(/^0+(\d)/, '$1');
                // 上限保护
                let num = v === '' ? '' : Math.min(parseInt(v, 10), 999);
                inp.value = num === '' ? '' : String(num);
            });

            // 失焦兜底：范围 [1, 999]
            inp.addEventListener('blur', () => {
                let num = parseInt(inp.value || '0', 10);
                if (isNaN(num) || num < 1) num = 1;
                if (num > 999) num = 999;
                inp.value = String(num);
            });
        } catch (e) {
            console.warn('配置数字输入限制失败', e);
        }
    });

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

    // 初始化显示状态 - 为所有模式生成初始conversation_id
    Array.from(document.getElementById('model-select').options).forEach(item => {
        const model = item.value
        if (!conversationIdStorage[model]) {
            conversationIdStorage[model] = generateConversationId();
        }
    });
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const fileUpload = document.getElementById('file-upload');
    fileUpload.setAttribute('accept', '*/*'); // 允许所有文件类型
    const uploadButton = document.getElementById('upload-button');
    const conversationHistory = document.getElementById('conversation-history');
    const uploadedFilesContainer = document.getElementById('uploaded-files-container');

    // 文件上传逻辑
    uploadButton.addEventListener('click', () => {
        fileUpload.click(); // 触发文件输入框的点击事件
    });

    fileUpload.addEventListener('change', async (event) => {
        const files = event.target.files;
        if (files.length === 0) {
            return;
        }

        // 禁用输入并切换按钮状态
        userInput.disabled = true;
        sendButton.disabled = true;
        uploadButton.disabled = true;
        uploadButton.innerHTML = '<svg class="loading-spinner-svg" viewBox="0 0 50 50"><circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle></svg>';
        uploadButton.classList.add('is-uploading'); // 添加上传中的类

        // 为每个文件创建上传中的占位符
        const filesToUpload = Array.from(files);
        const tempFileIds = []; // 用于存储临时文件ID，以便后续更新
        filesToUpload.forEach(file => {
            const tempId = `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            tempFileIds.push(tempId);
            uploadedFiles.push({ id: tempId, name: file.name, type: file.type, status: 'uploading' });
        });
        renderUploadedFiles(); // 立即渲染占位符

        const uploadPromises = filesToUpload.map(async (file, index) => {
            const tempId = tempFileIds[index]; // 获取对应的临时ID
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/uploadfile/', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const result = await response.json();

                // 找到对应的临时文件并更新其状态和信息
                const uploadedFileIndex = uploadedFiles.findIndex(f => f.id === tempId && f.status === 'uploading');
                if (uploadedFileIndex > -1) {
                    uploadedFiles[uploadedFileIndex] = {
                        id: result.id, // 使用后端返回的真实 ID
                        name: result.filename,
                        type: result.file_type, // 添加文件类型
                        fileAnalysis: result.file_analysis, // 使用更通用的 fileAnalysis
                        status: 'completed',
                        sent: false // 初始化为未发送状态
                    };
                } else {
                    // 如果没有找到临时文件（例如，多文件上传时只返回一个结果），则作为新文件添加
                    uploadedFiles.push({ id: result.id, name: result.filename, type: result.file_type, fileAnalysis: result.file_analysis, status: 'completed', sent: false });
                }
                renderUploadedFiles(); // 更新文件列表UI

            } catch (error) {
                console.error(`文件上传失败 (${file.name}):`, error);
                const errorElement = document.createElement('div');
                errorElement.className = 'history-item';
                errorElement.innerHTML = `<div class="qa-container"><div class="answer error">文件上传失败 (${file.name}): ${error.message}</div></div>`;
                conversationHistory.appendChild(errorElement);
                scrollToBottom();

                // 将对应的临时文件标记为失败
                const index = uploadedFiles.findIndex(f => f.id === tempId && f.status === 'uploading');
                if (index > -1) {
                    uploadedFiles[index].status = 'failed';
                }
                renderUploadedFiles(); // 更新UI以显示失败状态
            }
        });

        await Promise.all(uploadPromises).finally(() => {
            // 恢复UI状态
            userInput.disabled = false;
            sendButton.disabled = false;
            uploadButton.disabled = false;
            uploadButton.innerHTML = '📎';
            uploadButton.classList.remove('is-uploading'); // 移除上传中的类
            fileUpload.value = ''; // 清空文件输入，以便再次选择相同文件
        });
    });

    // 渲染已上传文件列表
    function renderUploadedFiles() {
        uploadedFilesContainer.innerHTML = ''; // 清空现有列表

        // 根据 uploadedFiles 数组的长度来控制容器的显示
        if (uploadedFiles.length > 0) {
            uploadedFilesContainer.style.display = 'flex'; // 有文件时显示
        } else {
            uploadedFilesContainer.style.display = 'none'; // 无文件时隐藏
        }

        uploadedFiles.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'uploaded-file-item';
            fileItem.dataset.fileId = file.id; // 添加data-file-id以便于查找和更新

            let fileContent = '';
            if (file.status === 'uploading') {
                fileItem.classList.add('uploading');
                fileContent = `
                    <div class="loading-spinner"></div>
                    <span>${file.name} (上传中...)</span>
                `;
            } else if (file.status === 'failed') {
                fileItem.classList.add('failed');
                fileContent = `
                    <span>${file.name} (上传失败)</span>
                    <button class="delete-file-btn" data-file-id="${file.id}" data-filename="${file.name}">x</button>
                `;
            } else { // completed
                let analysisSpan = '';
                if (file.fileAnalysis) {
                    analysisSpan = `<span class="file-analysis-preview" title="点击查看解析内容"> (已解析)</span>`;
                    fileItem.classList.add('has-file-analysis'); // 添加类以便于识别和添加事件
                    fileItem.dataset.fileAnalysis = file.fileAnalysis; // 存储解析内容
                    fileItem.dataset.fileType = file.type; // 存储文件类型
                }
                fileContent = `
                    <span>${file.name}</span>
                    ${analysisSpan}
                    <button class="delete-file-btn" data-file-id="${file.id}" data-filename="${file.name}">x</button>
                `;
            }
            fileItem.innerHTML = fileContent;
            uploadedFilesContainer.appendChild(fileItem);

            // 为带有文件解析的项添加点击事件
            if (file.fileAnalysis && file.status === 'completed') {
                fileItem.addEventListener('click', (event) => {
                    // 避免点击删除按钮时触发弹框
                    if (!event.target.classList.contains('delete-file-btn')) {
                        showFileAnalysisModal(file.name, file.fileAnalysis, file.type);
                    }
                });
            }
        });

        // 为删除按钮添加事件监听器
        uploadedFilesContainer.querySelectorAll('.delete-file-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                const fileIdToDelete = event.target.dataset.fileId; // 使用fileId
                const filenameToDelete = event.target.dataset.filename; // 同时传递filename给后端
                await deleteFile(fileIdToDelete, filenameToDelete);
            });
        });
    }

    // 删除文件
    async function deleteFile(fileId, filename) {
        try {
            // 立即从UI中移除文件项，并显示加载状态
            const fileItem = uploadedFilesContainer.querySelector(`[data-file-id="${fileId}"]`);
            if (fileItem) {
                fileItem.innerHTML = `<div class="loading-spinner"></div><span>${filename} (删除中...)</span>`;
                fileItem.classList.add('deleting');
            }

            const response = await fetch(`/deletefile/${fileId}`, { // 使用 fileId 进行删除
                method: 'DELETE',
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('文件删除成功:', result);

            // 从 uploadedFiles 数组中移除文件
            const index = uploadedFiles.findIndex(file => file.id === fileId);
            if (index > -1) {
                uploadedFiles.splice(index, 1);
            }
            renderUploadedFiles(); // 更新UI

        } catch (error) {
            console.error('文件删除失败:', error);
            // 如果删除失败，恢复文件项的显示，并标记为失败
            const fileItem = uploadedFilesContainer.querySelector(`[data-file-id="${fileId}"]`);
            if (fileItem) {
                fileItem.classList.remove('deleting');
                fileItem.classList.add('failed');
                fileItem.innerHTML = `<span>${filename} (删除失败)</span><button class="delete-file-btn" data-file-id="${fileId}" data-filename="${filename}">x</button>`;
            }
        }
    }

    // 用于存储累积的内容
    let currentExplanation = '';
    let currentAnswer = '';
    let currentActionGroup = null;
    let currentActionId = null;
    let currentIteration = 1; // 当前迭代计数

    // 自动滚动到底部的函数
    let isScrolling = false;
    let scrollTimeout = null;

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
        if (e.key === 'Enter' && !e.isComposing) { // 检查是否是回车键且不是输入法合成事件
            if (e.shiftKey) {
                // Shift+Enter 插入换行
                return;
            } else {
                // 单独Enter 触发提交
                e.preventDefault(); // 阻止默认的换行行为
                sendMessage();
            }
        }
    });

    // 监听 compositionend 事件，确保输入法完成输入后可以正常提交
    userInput.addEventListener('compositionend', e => {
        // 当输入法完成输入后，如果用户立即按 Enter，此时 isComposing 为 false，会触发 keydown 中的提交逻辑。
        // 这里不需要额外处理，因为 keydown 已经处理了。
    });

    userInput.addEventListener('paste', async (event) => {
        const items = event.clipboardData.items;
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.kind === 'file' && item.type.startsWith('image/')) {
                event.preventDefault(); // 阻止默认粘贴行为
                const file = item.getAsFile();
                if (file) {
                    // 禁用输入并切换按钮状态
                    userInput.disabled = true;
                    sendButton.disabled = true;
                    uploadButton.disabled = true;
                    uploadButton.innerHTML = '<svg class="loading-spinner-svg" viewBox="0 0 50 50"><circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle></svg>';
                    uploadButton.classList.add('is-uploading'); // 添加上传中的类

                    // 创建上传中的占位符
                    const tempId = `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                    uploadedFiles.push({ id: tempId, name: file.name || 'pasted_image.png', type: file.type, status: 'uploading' });
                    renderUploadedFiles(); // 立即渲染占位符

                    const formData = new FormData();
                    formData.append('file', file, file.name || 'pasted_image.png'); // 后端期望的字段名是 'file'

                    try {
                        const response = await fetch('/uploadfile/', {
                            method: 'POST',
                            body: formData,
                        });

                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }

                        const result = await response.json();
                        console.log('文件上传成功:', result);

                        // 找到对应的临时文件并更新其状态和信息
                        const uploadedFileIndex = uploadedFiles.findIndex(f => f.id === tempId && f.status === 'uploading');
                        if (uploadedFileIndex > -1) {
                            uploadedFiles[uploadedFileIndex] = {
                                id: result.id, // 使用后端返回的真实 ID
                                name: result.filename,
                                type: result.file_type, // 添加文件类型
                                fileAnalysis: result.file_analysis, // 使用更通用的 fileAnalysis
                                status: 'completed',
                                sent: false // 初始化为未发送状态
                            };
                        } else {
                            uploadedFiles.push({ id: result.id, name: result.filename, type: result.file_type, fileAnalysis: result.file_analysis, status: 'completed', sent: false });
                        }
                        renderUploadedFiles(); // 更新文件列表UI

                    } catch (error) {
                        console.error('文件上传失败:', error);
                        const errorElement = document.createElement('div');
                        errorElement.className = 'history-item';
                        errorElement.innerHTML = `<div class="qa-container"><div class="answer error">文件上传失败: ${error.message}</div></div>`;
                        conversationHistory.appendChild(errorElement);
                        scrollToBottom();

                        // 将临时文件标记为失败
                        const index = uploadedFiles.findIndex(f => f.id === tempId && f.status === 'uploading');
                        if (index > -1) {
                            uploadedFiles[index].status = 'failed';
                        }
                        renderUploadedFiles(); // 更新UI以显示失败状态
                    } finally {
                        // 恢复UI状态
                        userInput.disabled = false;
                        sendButton.disabled = false;
                        uploadButton.disabled = false;
                        uploadButton.innerHTML = '📎';
                        uploadButton.classList.remove('is-uploading'); // 移除上传中的类
                    }
                }
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

        const selectedModel = document.getElementById('model-select').value

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

        let query = userInput.value.trim();
        if (!query && uploadedFiles.length === 0) return;

        if (!query && uploadedFiles.length > 0) {
            query = '请总结文件内容。'; // 更通用的提示
        }

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
        questionTextDiv.innerHTML = renderMarkdownSafe(query);
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
            const selectedModul = document.getElementById('model-select').value;
            const conversation_id = conversationIdStorage[selectedModul]
            // 统一读取具体模型下拉（如果存在），并规范化为空值为 undefined
            const selectedModelName = document.getElementById('model-name-select').value;

            console.log('sendMessage: uploadedFiles array:', uploadedFiles); // 添加日志

            let response;

            // 其他模式使用 /chat 接口
            const requestBody = {
                query,
                modul: selectedModul,
                model_name: selectedModelName,
                conversation_id: conversation_id,
                itecount: parseInt(document.getElementById('itecount').value),
                conversation_round: parseInt(document.getElementById('conversation_count').value),
                file_ids: uploadedFiles.filter(file => !file.sent).map(file => file.id), // 只发送未发送过的文件
                tool_memory_enabled: document.getElementById('tool-memory-toggle').checked, // 工具洞察开关（会话级）
                sop_memory_enabled: document.getElementById('sop-memory-toggle').checked
            };

            // 如果是智能助手模式，添加工具调用参数
            if (selectedModul === 'chat') {
                const toolCallToggle = document.getElementById('tool-call-toggle');
                if (toolCallToggle) {
                    requestBody.enable_tools = toolCallToggle.checked;
                }
            }

            response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });


            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '创建会话失败');
            }

            // 保存chat_id并建立SSE连接
            currentChatId = result.chat_id;

            // 标记已发送的文件，避免下次重复发送
            uploadedFiles.forEach(file => {
                if (!file.sent) {
                    file.sent = true;
                }
            });

            // 启动延迟更新会话列表（8秒后执行，只调用一次）
            scheduleConversationListUpdate();

            const eventSource = new EventSource(`/stream/${result.chat_id}`);

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
                    streamTextContent: uiStreamTextContent, // 传递 streamTextContent
                    updatePlaybook: uiUpdatePlaybook, // 传递 uiUpdatePlaybook
                    fetchPlaybook: fetchPlaybook, // 传递 fetchPlaybook
                    currentModel: currentModel, // 传递当前模型
                    playbookStorage: playbookStorage, // 传递 playbook 存储对象
                    conversationIdStorage: conversationIdStorage, // 传递 conversationId 存储对象
                    scheduleConversationListUpdate: scheduleConversationListUpdate, // 传递延迟更新会话列表函数
                    scrollToBottom: scrollToBottom, // 传递滚动到底部函数
                    saveToKnowledgeBase: saveToKnowledgeBase, // 传递保存到知识库函数
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
// ===== 选项面板缓存功能 (24小时有效期) =====
document.addEventListener('DOMContentLoaded', () => {
    const OPTIONS_CACHE_KEY = 'proteus_options_cache';
    const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24小时（毫秒）

    // 获取所有选项元素
    const optionElements = {
        modelSelect: document.getElementById('model-select'),
        modelNameSelect: document.getElementById('model-name-select'),
        itecount: document.getElementById('itecount'),
        conversationCount: document.getElementById('conversation_count'),
        toolCallToggle: document.getElementById('tool-call-toggle'),
        toolmemoryToggle: document.getElementById('tool-memory-toggle'),
        sopMemoryToggle: document.getElementById('sop-memory-toggle')
    };

    /**
     * 保存选项到 localStorage，带时间戳
     */
    function saveOptionsToCache() {
        try {
            const options = {
                modelSelect: optionElements.modelSelect?.value || '',
                modelNameSelect: optionElements.modelNameSelect?.value || '',
                itecount: optionElements.itecount?.value || '25',
                conversationCount: optionElements.conversationCount?.value || '10',
                toolCallToggle: optionElements.toolCallToggle?.checked !== false,
                toolmemoryToggle: optionElements.toolmemoryToggle?.checked || false,
                sopMemoryToggle: optionElements.sopMemoryToggle?.checked || false,
                timestamp: Date.now()
            };
            localStorage.setItem(OPTIONS_CACHE_KEY, JSON.stringify(options));
            console.log('选项已缓存:', options);
        } catch (e) {
            console.warn('保存选项缓存失败:', e);
        }
    }

    /**
     * 从 localStorage 加载选项（检查24小时有效期）
     */
    function loadOptionsFromCache() {
        try {
            const cached = localStorage.getItem(OPTIONS_CACHE_KEY);
            if (!cached) return null;

            const options = JSON.parse(cached);
            const now = Date.now();

            // 检查缓存是否过期（24小时）
            if (!options.timestamp || (now - options.timestamp) > CACHE_DURATION) {
                console.log('选项缓存已过期，清除缓存');
                localStorage.removeItem(OPTIONS_CACHE_KEY);
                return null;
            }

            console.log('加载缓存的选项:', options);
            return options;
        } catch (e) {
            console.warn('加载选项缓存失败:', e);
            return null;
        }
    }

    /**
     * 应用缓存的选项到UI
     */
    function applyOptionsToUI(options) {
        if (!options) return;

        try {
            // 应用工作模式
            if (optionElements.modelSelect && options.modelSelect) {
                optionElements.modelSelect.value = options.modelSelect;
            }

            // 应用模型名称（需要等待模型列表加载完成）
            if (optionElements.modelNameSelect && options.modelNameSelect) {
                // 延迟设置，确保选项已加载
                const setModelName = () => {
                    if (optionElements.modelNameSelect.options.length > 0) {
                        optionElements.modelNameSelect.value = options.modelNameSelect;
                    } else {
                        setTimeout(setModelName, 100);
                    }
                };
                setModelName();
            }

            // 应用迭代轮次
            if (optionElements.itecount && options.itecount) {
                optionElements.itecount.value = options.itecount;
            }

            // 应用会话轮次
            if (optionElements.conversationCount && options.conversationCount) {
                optionElements.conversationCount.value = options.conversationCount;
            }

            // 应用工具调用开关
            if (optionElements.toolCallToggle && typeof options.toolCallToggle === 'boolean') {
                optionElements.toolCallToggle.checked = options.toolCallToggle;
            }

            // 应用工具记忆开关
            if (optionElements.memoryToggle && typeof options.memoryToggle === 'boolean') {
                optionElements.memoryToggle.checked = options.memoryToggle;
            }

            // 应用SOP记忆开关
            if (optionElements.sopMemoryToggle && typeof options.sopMemoryToggle === 'boolean') {
                optionElements.sopMemoryToggle.checked = options.sopMemoryToggle;
            }

            console.log('选项已应用到UI');
        } catch (e) {
            console.warn('应用选项到UI失败:', e);
        }
    }

    /**
     * 为所有选项元素添加change事件监听器
     */
    function attachChangeListeners() {
        Object.values(optionElements).forEach(element => {
            if (!element) return;

            const eventType = element.type === 'checkbox' ? 'change' : 'change';
            element.addEventListener(eventType, () => {
                saveOptionsToCache();
            });
        });
    }

    // 初始化：加载缓存的选项
    const cachedOptions = loadOptionsFromCache();
    if (cachedOptions) {
        applyOptionsToUI(cachedOptions);
    }

    // 附加change监听器以自动保存
    attachChangeListeners();

    // 页面卸载时保存一次（确保最新状态被保存）
    window.addEventListener('beforeunload', () => {
        saveOptionsToCache();
    });

    const modelSelect = document.getElementById('model-select');
    //工具调用容器
    const toolCallContainer = document.getElementById('tool-call-container');

    if (modelSelect) {

        // 当下拉变化时，触发对应菜单项的点击逻辑（复用现有处理）
        modelSelect.addEventListener('change', () => {
            const newModel = modelSelect.value;
            const target = modelSelect.options[modelSelect.selectedIndex];
            if (target) {
                // 触发菜单项的点击逻辑（会做历史保存/恢复等）
                target.click();
            }
            // 控制工具调用选项的显示
            updateToolCallDisplay(newModel);
        });

        // 更新工具调用选项显示状态
        function updateToolCallDisplay(selectedModel) {
            console.log('更新工具调用选项显示状态', selectedModel);
            if (toolCallContainer) {
                console.log('工具调用选项显示状态', toolCallContainer.style.display);
                if (selectedModel === 'chat') {
                    toolCallContainer.style.display = 'block';
                } else {
                    toolCallContainer.style.display = 'none';
                }
            }
        }

        // 初始化工具调用选项显示状态
        updateToolCallDisplay(modelSelect.value);
    }
});

// ===== Memory option for options-panel (persist selections locally, add help tooltip) =====
document.addEventListener('DOMContentLoaded', () => {
    try {
        const optionsPanel = document.getElementById('options-panel');
        const memoryWrapper = optionsPanel ? optionsPanel.querySelector('.memory-wrapper') : null;
        if (!memoryWrapper) return;

        // 使用页面内现有的"记忆"开关
        let toolmemoryToggle = document.getElementById('tool-memory-toggle');
        if (!toolmemoryToggle) return;

        // 兜底：使用 data-title 避免原生 title 产生第二种提示
        const help = document.querySelector('.memory-help');
        if (help) {
            if (!help.getAttribute('data-title')) {
                help.setAttribute('data-title', '开启后，将在本次会话记录并分析工具调用，用于优化后续调用；该状态会随请求传给后端参与决策。');
            }
            if (help.hasAttribute('title')) help.removeAttribute('title');
        }

        // 仅控制"工具洞察"开关（会话级），不再持久化 UI 参数
        const INSIGHT_KEY = 'tool_insight_enabled';

        function getInsightEnabled() {
            try { return sessionStorage.getItem(INSIGHT_KEY) === 'true'; } catch { return false; }
        }
        function setInsightEnabled(v) {
            try { sessionStorage.setItem(INSIGHT_KEY, v ? 'true' : 'false'); } catch { }
        }

        // 初始化 toggle（一次性迁移 legacy 的 localStorage -> sessionStorage）
        try {
            const legacy = (localStorage.getItem('options_memory_enabled') === 'true');
            const current = getInsightEnabled();
            if (!current && legacy) {
                setInsightEnabled(true);
                try { localStorage.removeItem('options_memory_enabled'); } catch { }
            }
            toolmemoryToggle.checked = getInsightEnabled();
        } catch {
            toolmemoryToggle.checked = getInsightEnabled();
        }

        // 切换 -> 更新会话状态（随请求传到后端）
        toolmemoryToggle.addEventListener('change', () => {
            setInsightEnabled(toolmemoryToggle.checked);
        });

        // 不再保存/恢复模型与参数；"记忆"仅表示开启会话级工具洞察
    } catch (e) {
        console.warn('初始化记忆选项失败:', e);
    }
});