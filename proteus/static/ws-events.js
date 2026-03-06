/**
 * ws-events.js
 *
 * WSEventSource —— 用 WebSocket 模拟 EventSource 接口的适配器。
 *
 * 后端 WebSocket 消息格式（JSON 字符串）:
 *   {"event": "event_name", "data": "<json_string_or_plain_string>"}
 *
 * 对外提供与 EventSource 完全兼容的 API：
 *   addEventListener(type, handler)
 *   removeEventListener(type, handler)
 *   close()
 *   onerror (getter / setter)
 */
export class WSEventSource {
    /**
     * @param {string} url  WebSocket URL，如 "ws://host/ws/stream/{chatId}"
     */
    constructor(url) {
        this._url = url;
        this._listeners = {};          // Map<eventType, Set<handler>>
        this._errorHandler = null;
        this._closed = false;
        this._receivedTerminalEvent = false;
        this._ws = null;
        this._connect();
    }

    _connect() {
        const ws = new WebSocket(this._url);
        this._ws = ws;

        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                const eventType = msg.event;
                // data 字段保持为字符串，与 SSE EventSource 的 event.data 一致
                const data = msg.data;

                if (!eventType) return;

                // 标记终态事件，避免 onclose 触发误报错误
                if (eventType === 'complete' || eventType === 'error') {
                    this._receivedTerminalEvent = true;
                }

                const handlers = this._listeners[eventType];
                if (handlers && handlers.size > 0) {
                    const syntheticEvent = { data };
                    handlers.forEach(handler => {
                        try {
                            handler(syntheticEvent);
                        } catch (e) {
                            console.error(`WSEventSource handler error for '${eventType}':`, e);
                        }
                    });
                }
            } catch (e) {
                console.error('WSEventSource 解析消息失败:', e, evt.data);
            }
        };

        ws.onerror = (e) => {
            if (typeof this._errorHandler === 'function') {
                this._errorHandler(e);
            }
        };

        ws.onclose = () => {
            // 连接意外断开（既没有收到终态事件，也没有主动调用 close()），触发错误处理
            if (!this._closed && !this._receivedTerminalEvent) {
                if (typeof this._errorHandler === 'function') {
                    this._errorHandler(new Event('error'));
                }
            }
        };
    }

    addEventListener(type, handler) {
        if (!this._listeners[type]) {
            this._listeners[type] = new Set();
        }
        this._listeners[type].add(handler);
    }

    removeEventListener(type, handler) {
        if (this._listeners[type]) {
            this._listeners[type].delete(handler);
        }
    }

    /**
     * onerror setter — 保持与 EventSource 的赋值方式兼容：
     *   eventSource.onerror = () => { ... }
     */
    set onerror(handler) {
        this._errorHandler = handler;
        // 同步更新底层 WebSocket 的 onerror，确保握手阶段的错误也能被捕获
        if (this._ws) {
            this._ws.onerror = (e) => {
                if (typeof this._errorHandler === 'function') {
                    this._errorHandler(e);
                }
            };
        }
    }

    get onerror() {
        return this._errorHandler;
    }

    close() {
        this._closed = true;
        if (
            this._ws &&
            (this._ws.readyState === WebSocket.OPEN ||
                this._ws.readyState === WebSocket.CONNECTING)
        ) {
            this._ws.close();
        }
    }
}

/**
 * 根据当前页面协议返回 WebSocket 基础 URL。
 * https → wss://host, http → ws://host
 * @returns {string}  例如 "wss://example.com" 或 "ws://localhost:8000"
 */
export function getWsBaseUrl() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}`;
}
