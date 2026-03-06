/**
 * ws-events-global.js
 *
 * 与 ws-events.js 功能相同，但以普通 <script> 标签加载（无 ES module export），
 * 将 WSEventSource 和 getWsBaseUrl 暴露为全局变量。
 */
(function (global) {
    'use strict';

    /**
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
    function WSEventSource(url) {
        this._url = url;
        this._listeners = {};
        this._errorHandler = null;
        this._closed = false;
        this._receivedTerminalEvent = false;
        this._ws = null;
        this._connect();
    }

    WSEventSource.prototype._connect = function () {
        var self = this;
        var ws = new WebSocket(this._url);
        this._ws = ws;

        ws.onmessage = function (evt) {
            try {
                var msg = JSON.parse(evt.data);
                var eventType = msg.event;
                var data = msg.data; // 保持为字符串，与 SSE EventSource.event.data 一致

                if (!eventType) return;

                if (eventType === 'complete' || eventType === 'error') {
                    self._receivedTerminalEvent = true;
                }

                var handlers = self._listeners[eventType];
                if (handlers && handlers.size > 0) {
                    var syntheticEvent = { data: data };
                    handlers.forEach(function (handler) {
                        try {
                            handler(syntheticEvent);
                        } catch (e) {
                            console.error('WSEventSource handler error for \'' + eventType + '\':', e);
                        }
                    });
                }
            } catch (e) {
                console.error('WSEventSource 解析消息失败:', e, evt.data);
            }
        };

        ws.onerror = function (e) {
            if (typeof self._errorHandler === 'function') {
                self._errorHandler(e);
            }
        };

        ws.onclose = function () {
            if (!self._closed && !self._receivedTerminalEvent) {
                if (typeof self._errorHandler === 'function') {
                    self._errorHandler(new Event('error'));
                }
            }
        };
    };

    WSEventSource.prototype.addEventListener = function (type, handler) {
        if (!this._listeners[type]) {
            this._listeners[type] = new Set();
        }
        this._listeners[type].add(handler);
    };

    WSEventSource.prototype.removeEventListener = function (type, handler) {
        if (this._listeners[type]) {
            this._listeners[type].delete(handler);
        }
    };

    Object.defineProperty(WSEventSource.prototype, 'onerror', {
        get: function () { return this._errorHandler; },
        set: function (handler) {
            this._errorHandler = handler;
            if (this._ws) {
                var self = this;
                this._ws.onerror = function (e) {
                    if (typeof self._errorHandler === 'function') {
                        self._errorHandler(e);
                    }
                };
            }
        }
    });

    WSEventSource.prototype.close = function () {
        this._closed = true;
        if (
            this._ws &&
            (this._ws.readyState === WebSocket.OPEN ||
                this._ws.readyState === WebSocket.CONNECTING)
        ) {
            this._ws.close();
        }
    };

    /**
     * 根据当前页面协议返回 WebSocket 基础 URL。
     * https → wss://host, http → ws://host
     * @returns {string}
     */
    function getWsBaseUrl() {
        var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return proto + '//' + window.location.host;
    }

    // 暴露为全局变量
    global.WSEventSource = WSEventSource;
    global.getWsBaseUrl = getWsBaseUrl;

}(typeof window !== 'undefined' ? window : this));
