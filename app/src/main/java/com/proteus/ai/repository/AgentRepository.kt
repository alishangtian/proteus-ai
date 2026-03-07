package com.proteus.ai.repository

import com.proteus.ai.api.ApiClient
import com.proteus.ai.api.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class AgentRepository {

    suspend fun getAgentsList(
        token: String,
        page: Int = 1,
        pageSize: Int = 20,
        status: String? = null
    ): AgentStatusListResponse = withContext(Dispatchers.IO) {
        ApiClient.apiService.getAgentsStatus("Bearer $token", page, pageSize, status)
    }

    suspend fun stopAgent(token: String, agentId: String): AgentActionResponse = withContext(Dispatchers.IO) {
        ApiClient.apiService.stopAgent("Bearer $token", agentId)
    }

    suspend fun deleteAgent(token: String, agentId: String): AgentActionResponse = withContext(Dispatchers.IO) {
        ApiClient.apiService.deleteAgent("Bearer $token", agentId)
    }
}
