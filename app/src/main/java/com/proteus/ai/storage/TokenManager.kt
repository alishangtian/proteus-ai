package com.proteus.ai.storage

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "proteus_prefs")

class TokenManager(private val context: Context) {

    companion object {
        private val TOKEN_KEY = stringPreferencesKey("bearer_token")
        private val SERVER_URL_KEY = stringPreferencesKey("server_url")
        
        // 默认使用本机地址（Android 模拟器访问宿主机器）
        const val DEFAULT_SERVER_URL = "http://10.0.2.2:8888/"
    }

    fun tokenFlow(): Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[TOKEN_KEY]
    }

    fun serverUrlFlow(): Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[SERVER_URL_KEY]
    }

    suspend fun saveToken(token: String) {
        context.dataStore.edit { prefs ->
            prefs[TOKEN_KEY] = token.trim()
        }
    }

    suspend fun saveServerUrl(url: String) {
        context.dataStore.edit { prefs ->
            val normalizedUrl = url.trim().let {
                if (!it.endsWith("/")) "$it/" else it
            }
            prefs[SERVER_URL_KEY] = normalizedUrl
        }
    }

    suspend fun clearToken() {
        context.dataStore.edit { prefs ->
            prefs.remove(TOKEN_KEY)
        }
    }

    suspend fun clearServerUrl() {
        context.dataStore.edit { prefs ->
            prefs.remove(SERVER_URL_KEY)
        }
    }
}
