package com.proteus.ai.ui.components

import android.annotation.SuppressLint
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun MermaidWebView(
    mermaidCode: String,
    modifier: Modifier = Modifier,
    applyHeightConstraints: Boolean = true
) {
    var hasError by remember { mutableStateOf(false) }

    if (hasError) {
        // 如果渲染出错，回退到普通文本显示
        Surface(
            modifier = modifier.fillMaxWidth().padding(vertical = 4.dp),
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(8.dp)
        ) {
            Text(
                text = "```mermaid\n$mermaidCode\n```",
                modifier = Modifier.padding(8.dp),
                style = MaterialTheme.typography.bodySmall.copy(
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp
                )
            )
        }
    } else {
        val html = """
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                <script>
                    mermaid.initialize({ 
                        startOnLoad: true, 
                        theme: 'default',
                        suppressErrorNotifications: true,
                        securityLevel: 'loose'
                    });
                    
                    // 监听渲染错误
                    window.onerror = function(msg, url, line, col, error) {
                        if (window.AndroidBridge) {
                            window.AndroidBridge.onError();
                        }
                        return true;
                    };
                </script>
                <style>
                    body { margin: 0; padding: 10px; display: flex; justify-content: center; }
                    #mermaid-container { width: 100%; }
                    .error { display: none !important; } /* 隐藏 mermaid 默认的错误 UI */
                </style>
            </head>
            <body>
                <div id="mermaid-container" class="mermaid">
                    $mermaidCode
                </div>
            </body>
            </html>
        """.trimIndent()

        AndroidView(
            factory = { context ->
                WebView(context).apply {
                    webViewClient = WebViewClient()
                    webChromeClient = object : WebChromeClient() {
                        override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                            if (consoleMessage?.message()?.contains("Error", ignoreCase = true) == true) {
                                hasError = true
                            }
                            return super.onConsoleMessage(consoleMessage)
                        }
                    }
                    settings.javaScriptEnabled = true
                    settings.loadWithOverviewMode = true
                    settings.useWideViewPort = true
                    setBackgroundColor(0)
                    
                    // 添加接口供 JS 调用回传错误
                    addJavascriptInterface(object {
                        @android.webkit.JavascriptInterface
                        fun onError() {
                            post { hasError = true }
                        }
                    }, "AndroidBridge")
                }
            },
            update = { webView ->
                webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null)
            },
            modifier = if (applyHeightConstraints) {
                modifier
                    .fillMaxWidth()
                    .heightIn(min = 100.dp, max = 500.dp)
            } else {
                modifier
            }
        )
    }
}
