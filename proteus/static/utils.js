// 通用工具函数
export function generateConversationId() {
    return Date.now().toString() + '-' + Math.random().toString(36).substr(2, 9);
}

export function sanitizeFilename(name) {
    return String(name || 'file')
        .replace(/[^a-zA-Z0-9\u4e00-\u9fa5\-_]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
}

export function getMimeType(format) {
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
    return mimeTypes[(format || '').toLowerCase()] || 'application/octet-stream';
}

export function downloadFileFromContent(content, filename, mime) {
    const blob = new Blob([content], { type: (mime || 'application/octet-stream') + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

export async function fetchJSON(url, options = {}) {
    const resp = await fetch(url, options);
    if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
    return await resp.json();
}