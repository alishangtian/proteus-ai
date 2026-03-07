package com.proteus.ai.ui

import com.proteus.ai.api.model.AgentConversationGroup
import com.proteus.ai.api.model.AgentInfo
import com.proteus.ai.api.model.withoutAgent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentMonitorScreenTest {

    @Test
    fun buildAgentSummary_aggregatesCountsAndTokensAcrossConversations() {
        val groups = listOf(
            AgentConversationGroup(
                conversationId = "conv-1",
                agents = listOf(
                    AgentInfo(status = "running", totalInputTokens = 1200, totalOutputTokens = 300),
                    AgentInfo(status = "complete", totalInputTokens = 800, totalOutputTokens = 200)
                ),
                hasRunning = true
            ),
            AgentConversationGroup(
                conversationId = "conv-2",
                agents = listOf(
                    AgentInfo(status = "error", totalInputTokens = 500, totalOutputTokens = 100)
                ),
                hasRunning = false
            )
        )

        val summary = buildAgentSummary(groups)

        assertEquals(2, summary.conversationCount)
        assertEquals(3, summary.agentCount)
        assertEquals(1, summary.runningCount)
        assertEquals(2500, summary.totalInputTokens)
        assertEquals(600, summary.totalOutputTokens)
    }

    @Test
    fun formatElapsedTime_formatsSecondsMinutesAndHours() {
        assertEquals("45s", formatElapsedTime(45.0))
        assertEquals("2m 5s", formatElapsedTime(125.0))
        assertEquals("1h 1m", formatElapsedTime(3665.0))
    }

    @Test
    fun formatTokenCount_shortensLargeValues() {
        assertEquals("999", formatTokenCount(999))
        assertEquals("1.5K", formatTokenCount(1500))
        assertEquals("2.5M", formatTokenCount(2_500_000))
    }

    @Test
    fun withoutAgent_recalculatesRunningStateAndKeepsRemainingAgents() {
        val group = AgentConversationGroup(
            conversationId = "conv-1",
            agents = listOf(
                AgentInfo(agentId = "a-1", status = "running"),
                AgentInfo(agentId = "a-2", status = "complete")
            ),
            hasRunning = true
        )

        val updated = group.withoutAgent("a-1")

        assertEquals(1, updated?.agents?.size)
        assertEquals("a-2", updated?.agents?.single()?.agentId)
        assertFalse(updated?.hasRunning ?: true)
    }

    @Test
    fun withoutAgent_returnsNullWhenLastAgentRemoved() {
        val group = AgentConversationGroup(
            conversationId = "conv-1",
            agents = listOf(AgentInfo(agentId = "a-1", status = "running")),
            hasRunning = true
        )

        assertNull(group.withoutAgent("a-1"))
    }

    @Test
    fun withoutAgent_keepsRunningFlagWhenRunningAgentStillExists() {
        val group = AgentConversationGroup(
            conversationId = "conv-1",
            agents = listOf(
                AgentInfo(agentId = "a-1", status = "running"),
                AgentInfo(agentId = "a-2", status = "running"),
                AgentInfo(agentId = "a-3", status = "complete")
            ),
            hasRunning = true
        )

        val updated = group.withoutAgent("a-3")

        assertTrue(updated?.hasRunning == true)
        assertEquals(2, updated?.agents?.count { it.status == "running" })
    }
}
