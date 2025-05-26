function renderSearchResults(action, data, currentActionId) {
    console.log('Rendering search results...', action, data);
    if (action !== 'serper_search' || !Array.isArray(data)) {
        console.error('Invalid search results data');
        return;
    }

    // 创建搜索结果容器
    const resultsContainer = document.createElement('div');
    resultsContainer.className = 'search-results';

    // 遍历搜索结果并创建卡片
    data.forEach(item => {
        const card = document.createElement('div');
        card.className = 'search-card';

        // 添加点击事件，点击卡片时在新标签页打开链接
        card.addEventListener('click', () => {
            window.open(item.link, '_blank');
        });

        // 标题
        const title = document.createElement('h3');
        title.className = 'title';
        title.textContent = item.title;
        card.appendChild(title);

        // 摘要
        const snippet = document.createElement('p');
        snippet.className = 'snippet';
        snippet.textContent = item.snippet;
        card.appendChild(snippet);

        // 来源
        const source = document.createElement('div');
        source.className = 'source';
        
        const sourceIcon = document.createElement('div');
        sourceIcon.className = 'source-icon';
        sourceIcon.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/></svg>`;
        
        const sourceText = document.createElement('span');
        sourceText.className = 'source-text';
        let hostname = '';
        try {
            hostname = new URL(item.link).hostname;
        } catch (e) {
            // 如果URL无效，尝试从link字符串中提取域名
            hostname = item.link.split('/')[2] || '未知来源';
        }
        sourceText.textContent = hostname;
        
        source.appendChild(sourceIcon);
        source.appendChild(sourceText);
        card.appendChild(source);

        // 链接
        const link = document.createElement('a');
        link.className = 'link';
        link.href = item.link;
        link.textContent = item.link;
        link.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        card.appendChild(link);

        // 操作按钮
        const actions = document.createElement('div');
        actions.className = 'actions';
        
        // 复制按钮
        const copyBtn = document.createElement('div');
        copyBtn.className = 'action-button';
        copyBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
            </svg>
            <span>复制</span>
        `;
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(item.link);
        });
        
        // 点赞按钮
        const likeBtn = document.createElement('div');
        likeBtn.className = 'action-button';
        likeBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>
            <span>点赞</span>
        `;
        
        actions.appendChild(copyBtn);
        actions.appendChild(likeBtn);
        card.appendChild(actions);
        resultsContainer.appendChild(card);
    });

    // 获取当前action组
    const actionGroup = document.querySelector('.action-group[data-action-id="' + currentActionId + '"]');
    if (actionGroup) {
        // 创建结果容器
        const completeDiv = document.createElement('div');
        completeDiv.setAttribute('data-action-id', currentActionId);
        completeDiv.className = 'action-complete';

        // 添加结果标签和时间戳
        completeDiv.innerHTML = `
            <span class="result-label">结果：</span>
            <span class="action-timestamp">${new Date().toLocaleTimeString()}</span>
        `;

        // 添加搜索结果卡片容器
        completeDiv.appendChild(resultsContainer);

        // 将结果添加到action组
        actionGroup.appendChild(completeDiv);
        return completeDiv
    }
}
