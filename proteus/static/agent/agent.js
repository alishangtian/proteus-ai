

document.addEventListener('DOMContentLoaded', () => {
    // 状态管理
    let selectedTools = new Set();
    let availableTools = [];
    let currentAgentId = null; // 当前编辑的智能体ID
    let isEditing = false; // 是否处于编辑状态

    // DOM元素
    const systemPrompt = document.getElementById('systemPrompt');
    const generatePromptBtn = document.getElementById('generatePromptButton');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const saveButton = document.getElementById('saveButton');
    const chatDisplay = document.getElementById('chatDisplay');
    const toolList = document.getElementById('toolList');
    const addToolBtn = document.getElementById('add-tool-button');
    const toolSelectorModal = document.getElementById('toolSelectorModal');
    const closeModal = document.querySelectorAll('.close-modal');
    const toolSelectorList = document.getElementById('toolSelectorList');
    const confirmSelection = document.querySelector('.confirm-selection');
    const agentListBtn = document.getElementById('agentListButton');
    const agentSelectorModal = document.getElementById('agentSelectorModal');
    const agentSelectorList = document.getElementById('agentSelectorList');
    const deleteAgentBtn = document.getElementById('deleteAgentButton');

    // 更新编辑状态
    function updateEditingState(editing) {
        isEditing = editing;
        deleteAgentBtn.style.display = editing ? 'block' : 'none';
    }

    updateEditingState(false); // 初始状态不显示删除按钮

    // 获取工具列表
    async function fetchTools() {
        try {
            const response = await fetch('/agents/nodes/tools');
            if (!response.ok) throw new Error('获取工具列表失败');
            
            const data = await response.json();
            console.log('工具列表API响应:', data);
            
            if (data && data.data && Array.isArray(data.data)) {
                // 按分类分组工具
                const toolsByCategory = {};
                console.log('工具列表数据:', data.data);
                data.data.forEach(tool => {
                    const category = tool.category || '其他';
                    if (!toolsByCategory[category]) {
                        toolsByCategory[category] = [];
                    }
                    toolsByCategory[category].push({
                        id: tool.id,
                        name: tool.name,
                        description: tool.description || '',
                        icon: tool.icon || '🛠️'
                    });
                });
                
                availableTools = data.data;
                renderToolSelector(toolsByCategory);
                console.log('工具分类:', toolsByCategory);
                
                // 添加搜索功能
                const searchInput = document.createElement('input');
                searchInput.type = 'text';
                searchInput.placeholder = '搜索工具...';
                searchInput.className = 'tool-search';
                searchInput.addEventListener('input', (e) => {
                    const searchTerm = e.target.value.toLowerCase();
                    document.querySelectorAll('.tool-item').forEach(item => {
                        const toolName = item.querySelector('label').textContent.toLowerCase();
                        item.style.display = toolName.includes(searchTerm) ? 'flex' : 'none';
                    });
                });
                
                toolSelectorList.prepend(searchInput);
            } else {
                throw new Error(data.message || '无效的工具列表数据');
            }
        } catch (error) {
            console.error('获取工具列表错误:', error);
            addMessageToChat('agent', `获取工具列表失败: ${error.message}`);
            
            // 显示错误状态
            toolSelectorList.innerHTML = `
                <div class="error-message">
                    <p>无法加载工具列表</p>
                    <button class="retry-btn">重试</button>
                </div>
            `;
            
            // 添加重试按钮事件
            document.querySelector('.retry-btn')?.addEventListener('click', fetchTools);
        }
    }

    // 渲染工具选择器
    function renderToolSelector(toolsByCategory) {
        toolSelectorList.innerHTML = '';
        
        // 按分类渲染工具
        Object.entries(toolsByCategory).forEach(([category, tools]) => {
            // 添加分类标题
            const categoryHeader = document.createElement('div');
            categoryHeader.className = 'category-header';
            categoryHeader.textContent = category;
            toolSelectorList.appendChild(categoryHeader);
            
            // 添加分类下的工具
            tools.forEach(tool => {
                const toolItem = document.createElement('div');
                toolItem.className = 'tool-item';
                toolItem.setAttribute('data-tooltip', tool.description);
                toolItem.innerHTML = `
                    <input type="checkbox" id="${tool.id}" ${selectedTools.has(tool.id) ? 'checked' : ''}>
                    <label for="${tool.id}">
                        <span class="tool-icon">${tool.icon}</span>
                        <span class="tool-name">${tool.name}</span>
                        <span class="tool-desc">${tool.description}</span>
                    </label>
                `;
                toolSelectorList.appendChild(toolItem);
            });
        });
    }

    // 渲染已选工具
    function renderSelectedTools() {
        toolList.innerHTML = '';
        Array.from(selectedTools).forEach(toolId => {
            const tool = availableTools.find(t => t.id === toolId);
            if (tool) {
                const toolItem = document.createElement('div');
                toolItem.className = 'tool-item';
                toolItem.innerHTML = `
                    <span>${tool.name}</span>
                    <div class="tool-settings">⚙️</div>
                `;
                toolList.appendChild(toolItem);
            }
        });
    }

    // 工具选择模态框处理
    addToolBtn.addEventListener('click', () => {
        fetchTools();
        toolSelectorModal.style.display = 'flex';
    });

    closeModal[0].addEventListener('click', () => {
        toolSelectorModal.style.display = 'none';
    });

    confirmSelection.addEventListener('click', () => {
        // 更新选中的工具
        selectedTools = new Set();
        document.querySelectorAll('#toolSelectorList input[type="checkbox"]:checked')
            .forEach(checkbox => selectedTools.add(checkbox.id));
        
        renderSelectedTools();
        toolSelectorModal.style.display = 'none';
    });

    // 发送消息处理
    function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        // 添加用户消息到聊天显示区
        addMessageToChat('user', message);

        // 模拟Agent响应
        setTimeout(() => {
            const response = `收到消息: "${message}"\n系统提示词: ${systemPrompt.value}\n已选择的工具: ${Array.from(selectedTools).join(', ')}`;
            addMessageToChat('agent', response);
        }, 1000);

        // 清空输入框
        messageInput.value = '';
    }

    // 添加消息到聊天显示区
    function addMessageToChat(type, content, status) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message${status ? ' ' + status : ''}`;
        messageDiv.textContent = content;
        chatDisplay.appendChild(messageDiv);
        
        // 滚动到最新消息
        chatDisplay.scrollTop = chatDisplay.scrollHeight;
    }

    // 事件监听器
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            if (!e.shiftKey) {
                // Enter发送消息
                e.preventDefault();
                sendMessage();
            }
            // Shift+Enter自动换行，不需要特殊处理，因为这是textarea的默认行为
        }
    });

    // 自动调整文本框高度
    messageInput.addEventListener('input', () => {
        // 保存滚动位置
        const scrollPos = messageInput.scrollTop;
        messageInput.style.height = 'auto';
        const newHeight = Math.min(Math.max(messageInput.scrollHeight, 50), 200); // 最小50px，最大200px
        messageInput.style.height = newHeight + 'px';
        // 恢复滚动位置
        messageInput.scrollTop = scrollPos;
    });

    // 系统提示词变更监听
    systemPrompt.addEventListener('input', () => {
        console.log('系统提示词已更新:', systemPrompt.value);
    });

    // 保存按钮点击处理
    saveButton.addEventListener('click', async () => {
        const saveButtonText = saveButton.textContent;
        saveButton.disabled = true;
        saveButton.textContent = '保存中...';
        
        try {
            // 收集表单数据
            const agentName = document.getElementById('agentName')?.value || '未命名Agent';
            const agentDescription = document.getElementById('agentDescription')?.value || '由系统创建的Agent';
            
            // 验证必填字段
            if (!systemPrompt.value.trim()) {
                throw new Error('系统提示词不能为空');
            }

            const data = {
                name: agentName,
                description: agentDescription,
                system_prompt: systemPrompt.value,
                tools: availableTools.filter(tool => selectedTools.has(tool.id)).map(tool => ({
                    id: tool.id,
                    name: tool.name,
                    config: {} // 工具配置
                })),
                config: {
                    created_at: new Date().toISOString(),
                    version: '1.0'
                }
            };
            
            const url = currentAgentId ? `/agents/info/${currentAgentId}` : '/agents/info';
            const method = currentAgentId ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || '保存失败');
            }
            
            const result = await response.json();
            console.log('保存成功:', result);
            
            // 显示保存成功提示
            const saveMessage = document.createElement('div');
            saveMessage.className = 'message agent-message success';
            saveMessage.textContent = '配置已成功保存';
            chatDisplay.appendChild(saveMessage);
            chatDisplay.scrollTop = chatDisplay.scrollHeight;
            
        } catch (error) {
            console.error('保存失败:', error);
            
            // 显示错误提示
            const errorMessage = document.createElement('div');
            errorMessage.className = 'message agent-message error';
            errorMessage.textContent = `保存失败: ${error.message}`;
            chatDisplay.appendChild(errorMessage);
            chatDisplay.scrollTop = chatDisplay.scrollHeight;
            
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = saveButtonText;
            
            // 3秒后移除提示消息
            setTimeout(() => {
                const messages = chatDisplay.querySelectorAll('.message.agent-message');
                if (messages.length > 5) { // 保留最近5条消息
                    for (let i = 0; i < messages.length - 5; i++) {
                        chatDisplay.removeChild(messages[i]);
                    }
                }
            }, 3000);
        }
    });

    // AI生成提示词处理(流式)
    generatePromptBtn.addEventListener('click', async () => {
        const originalText = generatePromptBtn.textContent;
        generatePromptBtn.disabled = true;
        generatePromptBtn.textContent = '生成中...';
        systemPrompt.value = ''; // 清空原有内容

        try {
            const response = await fetch('/agents/generate-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: document.getElementById('agentName').value,
                    description: document.getElementById('agentDescription').value,
                    tools: availableTools.filter(tool => selectedTools.has(tool.id)).map(tool => ({
                        name: tool.name,
                        description: tool.description || ''
                    }))
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || '生成提示词失败');
            }

            if (!response.body) {
                throw new Error('无法读取响应流');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let receivedText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                receivedText += chunk;
                systemPrompt.value = receivedText;
                systemPrompt.scrollTop = systemPrompt.scrollHeight; // 自动滚动到底部
            }

            addMessageToChat('agent', '提示词已生成完成', 'success');
        } catch (error) {
            console.error('生成提示词错误:', error);
            addMessageToChat('agent', `生成提示词失败: ${error.message}`, 'error');
        } finally {
            generatePromptBtn.disabled = false;
            generatePromptBtn.textContent = originalText;
        }
    });

    // 获取智能体列表
    async function fetchAgents() {
        try {
            const response = await fetch('/agents/list');
            if (!response.ok) throw new Error('获取智能体列表失败');
            
            const agents = await response.json();
            if (Array.isArray(agents)) {
                renderAgentSelector(agents);
                
                // 添加搜索功能
                const searchInput = document.createElement('input');
                searchInput.type = 'text';
                searchInput.placeholder = '搜索智能体...';
                searchInput.className = 'tool-search';
                searchInput.addEventListener('input', (e) => {
                    const searchTerm = e.target.value.toLowerCase();
                    document.querySelectorAll('.agent-item').forEach(item => {
                        const agentName = item.querySelector('label').textContent.toLowerCase();
                        item.style.display = agentName.includes(searchTerm) ? 'flex' : 'none';
                    });
                });
                
                agentSelectorList.prepend(searchInput);
            } else {
                throw new Error(data.message || '无效的智能体列表数据');
            }
        } catch (error) {
            console.error('获取智能体列表错误:', error);
            addMessageToChat('agent', `获取智能体列表失败: ${error.message}`, 'error');
            
            // 显示错误状态
            agentSelectorList.innerHTML = `
                <div class="error-message">
                    <p>无法加载智能体列表</p>
                    <button class="retry-btn">重试</button>
                </div>
            `;
            
            // 添加重试按钮事件
            document.querySelector('.retry-btn')?.addEventListener('click', fetchAgents);
        }
    }

    // 渲染智能体选择器
    function renderAgentSelector(agents) {
        agentSelectorList.innerHTML = '';
        
        agents.forEach(agent => {
            const agentItem = document.createElement('div');
            agentItem.className = 'agent-item tool-item';
            agentItem.setAttribute('data-tooltip', agent.description);
            agentItem.setAttribute('data-system-prompt', agent.system_prompt);
            agentItem.setAttribute('data-tools', JSON.stringify(agent.tools || []));
            agentItem.innerHTML = `
                <input type="radio" name="agent" id="agent-${agent.id}" value="${agent.id}">
                <label for="agent-${agent.id}">
                    <span class="tool-icon">🤖</span>
                    <span class="tool-name">${agent.name}</span>
                </label>
            `;
            agentSelectorList.appendChild(agentItem);
        });
    }

    // 智能体列表按钮点击事件
    agentListBtn.addEventListener('click', () => {
        fetchAgents();
        agentSelectorModal.style.display = 'flex';
    });

    // 智能体选择确认事件
    document.querySelectorAll('.confirm-selection')[1].addEventListener('click', () => {
        const selectedAgentId = document.querySelector('#agentSelectorList input[type="radio"]:checked')?.value;
        if (!selectedAgentId) return;
        
        // 获取选中的智能体
        const selectedAgent = document.querySelector(`#agentSelectorList input[type="radio"][value="${selectedAgentId}"]`);
        const agentName = selectedAgent.nextElementSibling.querySelector('.tool-name').textContent;
        const agentDesc = selectedAgent.parentElement.getAttribute('data-tooltip');
        
        // 填充表单字段
        document.getElementById('agentName').value = agentName;
        document.getElementById('agentDescription').value = agentDesc;
        systemPrompt.value = selectedAgent.parentElement.getAttribute('data-system-prompt') || '';
        
        // 渲染工具列表
        const toolsData = JSON.parse(selectedAgent.parentElement.getAttribute('data-tools') || []);
        selectedTools = new Set(toolsData.map(tool => tool.id));
        availableTools = toolsData;
        renderSelectedTools();
        
        // 设置当前编辑状态
        currentAgentId = selectedAgentId;
        updateEditingState(true);
        
        // 保存当前编辑的智能体ID
        currentAgentId = selectedAgentId;
        
        agentSelectorModal.style.display = 'none';
    });

    // 删除智能体处理
    deleteAgentBtn.addEventListener('click', async () => {
        const selectedAgentId = document.querySelector('#agentSelectorList input[type="radio"]:checked')?.value;
        if (!selectedAgentId) {
            addMessageToChat('agent', '请先选择要删除的智能体', 'error');
            return;
        }

        // 确认删除
        const agentName = document.querySelector(`#agentSelectorList input[type="radio"][value="${selectedAgentId}"]`)
            .nextElementSibling.querySelector('.tool-name').textContent;
        
        if (!confirm(`确定要删除智能体 "${agentName}" 吗？此操作不可撤销！`)) {
            return;
        }

        try {
            const response = await fetch(`/agents/info/${selectedAgentId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || '删除失败');
            }

            addMessageToChat('agent', `智能体 "${agentName}" 已成功删除`, 'success');
            
            // 如果删除的是当前编辑的智能体，清空表单
            if (currentAgentId === selectedAgentId) {
                document.getElementById('agentName').value = '';
                document.getElementById('agentDescription').value = '';
                systemPrompt.value = '';
                selectedTools = new Set();
                renderSelectedTools();
                currentAgentId = null;
            }

            // 刷新智能体列表
            await fetchAgents();
        } catch (error) {
            console.error('删除智能体错误:', error);
            addMessageToChat('agent', `删除智能体失败: ${error.message}`, 'error');
        }
    });

    // 关闭模态框事件
    document.querySelector('#agentSelectorModal .close-modal').addEventListener('click', () => {
        agentSelectorModal.style.display = 'none';
    });
});
