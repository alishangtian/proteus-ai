package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class SimpleResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String?
)
