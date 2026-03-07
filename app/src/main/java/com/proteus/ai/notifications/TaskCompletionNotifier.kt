package com.proteus.ai.notifications

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.proteus.ai.MainActivity
import com.proteus.ai.ProteusAIApplication
import com.proteus.ai.R
import com.proteus.ai.api.model.AgentConversationGroup

private const val MAX_NOTIFICATION_TEXT_LENGTH = 80

data class ConversationCompletionNotice(
    val conversationId: String,
    val title: String,
    val message: String
)

internal fun detectConversationCompletionNotices(
    previous: List<AgentConversationGroup>,
    current: List<AgentConversationGroup>
): List<ConversationCompletionNotice> {
    if (previous.isEmpty()) return emptyList()

    val previousByConversationId = previous.associateBy { it.conversationId }
    return current.mapNotNull { group ->
        val previousGroup = previousByConversationId[group.conversationId] ?: return@mapNotNull null
        if (!previousGroup.hasRunning || group.hasRunning) return@mapNotNull null

        val normalizedStatuses = group.agents.map { it.status.lowercase() }
        val hasError = normalizedStatuses.any { it == "error" }
        val hasComplete = normalizedStatuses.any { it == "complete" }
        if (!hasError && !hasComplete) return@mapNotNull null

        val displayName = group.title.ifBlank { group.conversationId.ifBlank { "未关联会话" } }
        val title = if (hasError) "会话任务已结束" else "会话任务已完成"
        val message = if (hasError) {
            "$displayName 中的运行任务已结束，包含错误状态"
        } else {
            "$displayName 中的运行任务已全部完成"
        }
        ConversationCompletionNotice(
            conversationId = group.conversationId,
            title = title,
            message = message
        )
    }
}

class TaskCompletionNotifier(
    private val context: Context
) {
    fun notifyTaskCompleted(chatId: String, taskText: String) {
        notify(
            notificationId = "task-complete:$chatId".hashCode(),
            title = "任务已完成",
            message = taskText.ifBlank { "Proteus AI 任务执行完成" }
        )
    }

    fun notifyTaskFailed(chatId: String, errorMessage: String) {
        notify(
            notificationId = "task-error:$chatId".hashCode(),
            title = "任务执行出错",
            message = errorMessage.ifBlank { "Proteus AI 任务执行过程中发生错误" }
        )
    }

    fun notifyConversationCompleted(notice: ConversationCompletionNotice) {
        notify(
            notificationId = "conversation:${notice.conversationId}".hashCode(),
            title = notice.title,
            message = notice.message
        )
    }

    private fun notify(notificationId: Int, title: String, message: String) {
        if (!canPostNotifications()) return

        val notification = NotificationCompat.Builder(context, ProteusAIApplication.CHANNEL_ID)
            .setSmallIcon(R.drawable.proteus)
            .setContentTitle(title)
            .setContentText(message.trimForNotification())
            .setStyle(NotificationCompat.BigTextStyle().bigText(message.trimForNotification()))
            .setContentIntent(createOpenAppIntent())
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        NotificationManagerCompat.from(context).notify(notificationId, notification)
    }

    private fun canPostNotifications(): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            return false
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return true
        }
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun createOpenAppIntent(): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        return PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}

private fun String.trimForNotification(): String =
    replace("\\s+".toRegex(), " ").trim().take(MAX_NOTIFICATION_TEXT_LENGTH)
