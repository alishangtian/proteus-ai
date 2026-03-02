package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class ModelsResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("models") val models: List<String>
)