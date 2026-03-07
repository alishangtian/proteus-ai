package com.proteus.ai.notifications

import com.proteus.ai.api.model.AgentConversationGroup
import com.proteus.ai.api.model.AgentInfo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskCompletionNotifierTest {

    @Test
    fun detectConversationCompletionNotices_returnsNoticeWhenConversationStopsRunning() {
        val previous = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "研究任务",
                agents = listOf(AgentInfo(agentId = "a-1", status = "running")),
                hasRunning = true
            )
        )
        val current = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "研究任务",
                agents = listOf(AgentInfo(agentId = "a-1", status = "complete")),
                hasRunning = false
            )
        )

        val notices = detectConversationCompletionNotices(previous, current)

        assertEquals(1, notices.size)
        assertEquals("会话任务已完成", notices.single().title)
        assertTrue(notices.single().message.contains("研究任务"))
    }

    @Test
    fun detectConversationCompletionNotices_marksErrorTransitionsAsEnded() {
        val previous = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "批处理",
                agents = listOf(AgentInfo(agentId = "a-1", status = "running")),
                hasRunning = true
            )
        )
        val current = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "批处理",
                agents = listOf(AgentInfo(agentId = "a-1", status = "error")),
                hasRunning = false
            )
        )

        val notices = detectConversationCompletionNotices(previous, current)

        assertEquals(1, notices.size)
        assertEquals("会话任务已结束", notices.single().title)
    }

    @Test
    fun detectConversationCompletionNotices_ignoresInitialSnapshot() {
        val current = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "初始化",
                agents = listOf(AgentInfo(agentId = "a-1", status = "complete")),
                hasRunning = false
            )
        )

        val notices = detectConversationCompletionNotices(emptyList(), current)

        assertTrue(notices.isEmpty())
    }

    @Test
    fun detectConversationCompletionNotices_ignoresStopOnlyTransitions() {
        val previous = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "已停止任务",
                agents = listOf(AgentInfo(agentId = "a-1", status = "running")),
                hasRunning = true
            )
        )
        val current = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                title = "已停止任务",
                agents = listOf(AgentInfo(agentId = "a-1", status = "stopped")),
                hasRunning = false
            )
        )

        val notices = detectConversationCompletionNotices(previous, current)

        assertTrue(notices.isEmpty())
    }
}
