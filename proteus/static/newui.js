import Icons from './icons.js';
import { generateConversationId, sanitizeFilename, getMimeType, downloadFileFromContent, fetchJSON } from './utils.js';
import { scrollToBottom as uiScrollToBottom, resetUI as uiResetUI, renderNodeResult as uiRenderNodeResult, renderExplanation as uiRenderExplanation, renderAnswer as uiRenderAnswer, createQuestionElement, streamTextContent as uiStreamTextContent } from './ui.js';
import { registerSSEHandlers } from './sse-handlers.js';

// 临时存储历史对话数据 {model: htmlContent}
const historyStorage = {};
// 存储每个模型的conversation_id {model: conversationId}
const conversationIdStorage = {};
// 存储已上传文件的全局数组
const uploadedFiles = [];

// 存储当前chat_id和处理状态的全局变量
let currentChatId = null;
let isProcessing = false;
let currentModel = "super-agent"; // 默认模型
let currentConversationId = null; // 当前会话的conversation_id
const showIterationModels = ["super-agent", "home", "mcp-agent", "multi-agent", "browser-agent", "deep-research", "codeact-agent"]; // 假设这些模型需要迭代计数

document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.querySelector('.sidebar');
    const menuButton = document.querySelector('.menu-button');
    const newChatButton = document.querySelector('.new-chat button:first-child'); // "发起新对话" 按钮
    const recentChatsList = document.querySelector('.recent-chats ul');
    const chatContent = document.querySelector('.chat-content'); // 用于显示欢迎消息或聊天历史
    const modelSelector = document.querySelector('.model-selector select'); // 模型选择下拉框
    const userInput = document.querySelector('.chat-input-wrapper textarea');
    const voiceInputButton = document.querySelector('.voice-input-button');
    const uploadButton = document.getElementById('upload-button'); // 文件上传按钮
    const fileUploadInput = document.getElementById('file-upload'); // 隐藏的文件输入框
    const uploadedFilesContainer = document.getElementById('uploaded-files-container'); // 已上传文件容器
    const toolsActionButton = document.querySelector('.input-actions button:last-child'); // "工具" 按钮

    // 侧边栏菜单按钮点击事件
    if (menuButton) {
        menuButton.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            // 可以选择保存状态到本地存储
            // localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
    }

    // "发起新对话" 按钮点击事件
    if (newChatButton) {
        newChatButton.addEventListener('click', function () {
            // 清空当前对话历史
            chatContent.innerHTML = `
                <div class="welcome-message">
                    <h1>你好！ Neil</h1>
                </div>
                <div class="input-area">
                    <div class="chat-input-wrapper">
                        <textarea placeholder="问问 Gemini"></textarea>
                        <button class="voice-input-button"><i class="material-icons">mic</i></button>
                    </div>
                    <div class="input-actions">
                        <input type="file" id="file-upload" style="display: none;" multiple>
                        <button id="upload-button"><i class="material-icons">add</i></button>
                        <button><i class="material-icons">extension</i>工具</button>
                    </div>
                    <div id="uploaded-files-container" class="uploaded-files-container">
                        <!-- 已上传文件将在这里显示 -->
                    </div>
                </div>
            `;
            // 生成新的 conversation_id
            currentConversationId = generateConversationId();
            // 重置 UI 状态
            resetUI();
            // 重新绑定输入区域的事件
            bindInputAreaEvents();
        });
    }

    // 模型选择器 change 事件
    if (modelSelector) {
        modelSelector.addEventListener('change', function () {
            currentModel = this.value;
            // 这里可以添加逻辑来加载不同模型的历史对话，如果需要的话
            console.log('当前选择的模型:', currentModel);
            updateIterationDisplay(); // 在模型改变时更新迭代次数和对话轮次显示
        });
    }

    // 获取模型列表并填充选择器
    async function fetchModelsAndPopulateSelector() {
        try {
            const response = await fetch('/models');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.success && data.models && modelSelector) {
                modelSelector.innerHTML = ''; // 清空现有选项
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    modelSelector.appendChild(option);
                });
                // 设置默认选中项为第一个模型，或者之前保存的 currentModel
                if (data.models.length > 0) {
                    currentModel = modelSelector.value; // 更新 currentModel 为实际选中的值
                }
                console.log('模型列表已更新:', data.models);
            }
        } catch (error) {
            console.error('获取模型列表失败:', error);
            // 可以添加一个错误消息到UI
            if (modelSelector) {
                modelSelector.innerHTML = '<option value="">加载模型失败</option>';
                modelSelector.disabled = true;
            }
        }
    }
 
    // 更新迭代次数和对话轮次显示状态的函数
    function updateIterationDisplay() {
        const itecountContainer = document.getElementById('itecount-container');
        const conversationCountContainer = document.getElementById('conversation_count-container');
 
        if (showIterationModels.includes(currentModel)) {
            if (itecountContainer) itecountContainer.style.display = 'inline-block';
            if (conversationCountContainer) conversationCountContainer.style.display = 'inline-block';
        } else {
            if (itecountContainer) itecountContainer.style.display = 'none';
            if (conversationCountContainer) conversationCountContainer.style.display = 'none';
        }
    }
 
    // 在页面加载时调用
    fetchModelsAndPopulateSelector().then(() => {
        // 确保在模型加载并设置 currentModel 后再更新显示
        updateIterationDisplay();
    });
 
    // 绑定输入区域事件
    function bindInputAreaEvents() {
        const currentUserInput = document.querySelector('.chat-input-wrapper textarea');
        const currentVoiceInputButton = document.querySelector('.voice-input-button');
        const currentUploadButton = document.getElementById('upload-button');
        const currentFileUploadInput = document.getElementById('file-upload');
        const currentToolsActionButton = document.querySelector('.input-actions button:last-child');

        // 确保事件只绑定一次，或者在重新绑定前移除旧的监听器
        // 这里为了简化，假设每次调用 bindInputAreaEvents 都是在新的 DOM 元素上绑定
        if (currentUserInput) {
            currentUserInput.addEventListener('keydown', e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            // TODO: 添加粘贴事件处理
        }

        if (currentVoiceInputButton) {
            currentVoiceInputButton.addEventListener('click', () => {
                alert('语音输入功能待实现'); // 占位符
            });
        }

        // 文件上传逻辑
        if (currentUploadButton) {
            currentUploadButton.addEventListener('click', () => {
                currentFileUploadInput.click(); // 触发文件输入框的点击事件
            });
        }

        if (currentFileUploadInput) {
            currentFileUploadInput.addEventListener('change', async (event) => {
                const files = event.target.files;
                if (files.length === 0) {
                    return;
                }

                // 禁用输入并切换按钮状态
                currentUserInput.disabled = true;
                currentUploadButton.disabled = true;
                currentUploadButton.innerHTML = '<i class="material-icons">hourglass_empty</i>上传中...'; // 更新按钮图标和文本

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
                                status: 'completed'
                            };
                        } else {
                            // 如果没有找到临时文件（例如，多文件上传时只返回一个结果），则作为新文件添加
                            uploadedFiles.push({ id: result.id, name: result.filename, type: result.file_type, fileAnalysis: result.file_analysis, status: 'completed' });
                        }
                        renderUploadedFiles(); // 更新文件列表UI

                    } catch (error) {
                        console.error(`文件上传失败 (${file.name}):`, error);
                        const errorElement = document.createElement('div');
                        errorElement.className = 'chat-message error';
                        errorElement.innerHTML = `<p>文件上传失败 (${file.name}): ${error.message}</p>`;
                        chatContent.appendChild(errorElement);
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
                    currentUserInput.disabled = false;
                    currentUploadButton.disabled = false;
                    currentUploadButton.innerHTML = '<i class="material-icons">add</i>'; // 恢复按钮图标
                    currentFileUploadInput.value = ''; // 清空文件输入，以便再次选择相同文件
                });
            });
        }

        if (currentToolsActionButton) {
            currentToolsActionButton.addEventListener('click', () => {
                alert('工具功能待实现'); // 占位符
            });
        }
    }

    // 初始绑定事件
    bindInputAreaEvents();

    // 渲染已上传文件列表 (从 main.js 复制，并根据 newui 调整)
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
                    <button class="delete-file-btn" data-file-id="${file.id}" data-filename="${file.name}"><i class="material-icons">close</i></button>
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
                    <button class="delete-file-btn" data-file-id="${file.id}" data-filename="${file.name}"><i class="material-icons">close</i></button>
                `;
            }
            fileItem.innerHTML = fileContent;
            uploadedFilesContainer.appendChild(fileItem);

            // 为带有文件解析的项添加点击事件
            if (file.fileAnalysis && file.status === 'completed') {
                fileItem.addEventListener('click', (event) => {
                    // 避免点击删除按钮时触发弹框
                    if (!event.target.classList.contains('delete-file-btn') && !event.target.closest('.delete-file-btn')) {
                        showFileAnalysisModal(file.name, file.fileAnalysis, file.type);
                    }
                });
            }
        });

        // 为删除按钮添加事件监听器
        uploadedFilesContainer.querySelectorAll('.delete-file-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                const fileIdToDelete = event.currentTarget.dataset.fileId; // 使用 currentTarget
                const filenameToDelete = event.currentTarget.dataset.filename;
                await deleteFile(fileIdToDelete, filenameToDelete);
            });
        });
    }

    // 删除文件 (从 main.js 复制)
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
                fileItem.innerHTML = `<span>${filename} (删除失败)</span><button class="delete-file-btn" data-file-id="${fileId}" data-filename="${filename}"><i class="material-icons">close</i></button>`;
            }
        }
    }

    // 显示文件解析结果的弹框 (从 main.js 复制)
    function showFileAnalysisModal(filename, content, fileType) {
        const modal = document.getElementById('toolResultModal');
        // 如果 newui.html 中没有 toolResultModal，需要添加
        if (!modal) {
            console.warn('未找到 #toolResultModal 元素，无法显示文件解析弹框。');
            return;
        }
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

    // 简单的 HTML 清理函数 (从 main.js 复制)
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
            Array.from(el.attributes).forEach(attr => {
                const name = attr.name.toLowerCase();
                const val = (attr.value || '').toLowerCase();
                if (name.startsWith('on')) {
                    el.removeAttribute(attr.name);
                } else if ((name === 'href' || name === 'src' || name === 'xlink:href') && val.startsWith('javascript:')) {
                    el.removeAttribute(attr.name);
                } else if (name === 'style') {
                    el.removeAttribute('style');
                }
            });
        }
        toRemove.forEach(n => n.remove());
        return template.innerHTML;
    }

    // 将 Markdown 渲染为 HTML 并通过 sanitizeHTML 过滤后返回安全的 HTML (从 main.js 复制)
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

    // marked 库的配置 (从 main.js 复制)
    marked.use({
        gfm: true,
        tables: true,
        breaks: false,
        pedantic: false,
        smartLists: true,
        smartypants: false,
        gfm: true,
        breaks: true,
        baseUrl: null,
        xhtml: false,
        xhtml: true,
        mangle: false,
        headerIds: false,
        headerPrefix: '',
        langPrefix: 'hljs ',
        sanitize: false,
        highlight: (code, lang) => {
            try {
                return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
            } catch (e) {
                return hljs.highlightAuto(code).value;
            }
        },
        baseUrl: null,
        listItemIndent: '1'
    });

    // 重置 UI 状态的函数 (从 main.js 复制，并根据 newui 调整)
    function resetUI() {
        isProcessing = false;
        const currentUserInput = document.querySelector('.chat-input-wrapper textarea');
        if (currentUserInput) {
            currentUserInput.value = '';
            currentUserInput.disabled = false;
            currentUserInput.focus();
        }
        // 清空已上传文件列表
        uploadedFiles.length = 0;
        renderUploadedFiles();
    }

    // 停止执行的函数 (从 main.js 复制)
    async function stopExecution() {
        if (!currentChatId) return;

        const selectedModel = currentModel;

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

            const answerElement = document.querySelector('.chat-content .bot-message:last-child');
            if (answerElement) {
                const stopMessage = document.createElement('div');
                stopMessage.className = 'status-message';
                stopMessage.textContent = '已停止执行';
                answerElement.appendChild(stopMessage);
            }

            resetUI();
        } catch (error) {
            console.error('停止执行失败:', error);
            const answerElement = document.querySelector('.chat-content .bot-message:last-child');
            if (answerElement) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = `停止执行失败: ${error.message}`;
                answerElement.appendChild(errorDiv);
            }
            resetUI();
        }
    }

    // 自动滚动到底部的函数 (从 main.js 复制)
    let isScrolling = false;
    let scrollTimeout = null;
    function scrollToBottom() {
        const conversationHistory = chatContent; // newui 中直接使用 chatContent 作为滚动容器
        if (conversationHistory) {
            // 避免频繁滚动，设置一个小的延迟
            if (isScrolling) {
                clearTimeout(scrollTimeout);
            }
            isScrolling = true;
            scrollTimeout = setTimeout(() => {
                conversationHistory.scrollTop = conversationHistory.scrollHeight;
                isScrolling = false;
            }, 100);
        }
    }

    // 提交用户输入的全局函数 (从 main.js 复制，并根据 newui 调整)
    async function submitUserInput(nodeId, inputType, prompt, agentId = undefined) {
        const inputField = document.getElementById(`user-input-${nodeId}`);
        if (!inputField) return;

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

        const buildPayload = (node_id, val) => {
            const payload = {
                node_id,
                value: val,
                chat_id: currentChatId
            };
            if (agentId !== undefined && agentId !== null) {
                payload.agent_id = agentId;
            } else if (inputField && inputField.dataset && inputField.dataset.agentId) {
                payload.agent_id = inputField.dataset.agentId;
            } else if (submitButton && submitButton.dataset && submitButton.dataset.agentId) {
                payload.agent_id = submitButton.dataset.agentId;
            }
            return payload;
        };

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
                    const port = value;

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
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            (position) => {
                                const locationData = {
                                    latitude: position.coords.latitude,
                                    longitude: position.coords.longitude,
                                    accuracy: position.coords.accuracy,
                                    timestamp: position.timestamp
                                };

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
                                        const submitButtonEl = container.nextElementSibling;
                                        if (submitButtonEl) {
                                            submitButtonEl.remove();
                                        }
                                    }
                                }

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
                        return;
                    } else {
                        throw new Error('浏览器不支持地理位置功能');
                    }
                default:
                    break;
            }

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

    // 发送消息的骨架 (从 main.js 复制，并根据 newui 调整)
    async function sendMessage() {
        const currentUserInput = document.querySelector('.chat-input-wrapper textarea');
        let text = currentUserInput.value.trim();

        if (isProcessing) {
            stopExecution();
            return;
        }

        if (!text && uploadedFiles.length === 0) return;

        if (!text && uploadedFiles.length > 0) {
            text = '请总结文件内容。';
        }

        // 禁用输入
        currentUserInput.disabled = true;
        isProcessing = true;

        // 创建消息元素
        const questionElement = document.createElement('div');
        questionElement.className = 'chat-message user-message';
        questionElement.innerHTML = `<p>${renderMarkdownSafe(text)}</p>`;

        const answerElement = document.createElement('div');
        answerElement.className = 'chat-message bot-message';
        answerElement.innerHTML = `<p>思考中...</p>`;

        chatContent.appendChild(questionElement);
        chatContent.appendChild(answerElement);

        scrollToBottom();

        try {
            const selectedModel = currentModel;
            const selectedModelName = undefined;

            console.log('sendMessage: uploadedFiles array:', uploadedFiles);

            let response;
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
                    conversation_round: parseInt(document.getElementById('conversation_count').value) || 5,
                    file_ids: uploadedFiles.map(file => file.id)
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '创建会话失败');
            }

            currentChatId = result.chat_id;
            const eventSource = new EventSource(`stream/${result.chat_id}`);

            try {
                const toolExecutions = {};
                registerSSEHandlers(eventSource, {
                    answerElement: answerElement,
                    toolExecutions: toolExecutions,
                    currentActionIdRef: { value: null },
                    currentIterationRef: { value: 1 },
                    renderNodeResult: uiRenderNodeResult,
                    renderExplanation: uiRenderExplanation,
                    renderAnswer: uiRenderAnswer,
                    createQuestionElement: createQuestionElement,
                    Icons: Icons,
                    submitUserInput: submitUserInput, // 现在可以传入 submitUserInput
                    streamTextContent: uiStreamTextContent,
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

    // 初始化 currentConversationId
    currentConversationId = generateConversationId();
});