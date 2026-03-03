import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application") version "8.5.0"
    id("org.jetbrains.kotlin.android") version "1.9.24"
}

// Load keystore properties
val keystorePropertiesFile = rootProject.file("keystore.properties")
val keystoreProperties = Properties()
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "com.proteus.ai"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.proteus.ai"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }

        // 将 API 基础 URL 作为 BuildConfig 字段
        buildConfigField("String", "BASE_URL", "\"http://10.0.2.2:8888/\"")
    }

    signingConfigs {
        create("release") {
            storeFile = file(keystoreProperties["storeFile"] as String)
            storePassword = keystoreProperties["storePassword"] as String
            keyAlias = keystoreProperties["keyAlias"] as String
            keyPassword = keystoreProperties["keyPassword"] as String
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Release 构建使用生产环境 URL
            buildConfigField("String", "BASE_URL", "\"https://api.proteus-ai.com/\"")
            // 使用签名配置
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            // Debug 构建启用日志
            buildConfigField("boolean", "ENABLE_LOGGING", "true")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

// 排除 git-ignored 的 data/ 包（保留 storage/ 中的 TokenManager）
afterEvaluate {
    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        exclude("**/com/proteus/ai/data/**")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.2")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation(platform("androidx.compose:compose-bom:2024.10.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    // ViewModel
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.2")
    // Retrofit for HTTP
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    // OkHttp (SSE streaming)
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // DataStore for token storage
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    // Okio (used in ChatRepository for SSE buffer reading)
    implementation("com.squareup.okio:okio:3.9.0")
    // Timber for logging
    implementation("com.jakewharton.timber:timber:5.0.1")
    // Pull refresh
    implementation("androidx.compose.material:material:1.6.8")
    
    // Markdown rendering support
    // Remove compose-markdown to avoid conflict with richtext
    // implementation("com.github.jeziellago:compose-markdown:0.5.0")

    // Richtext with commonmark 0.21.0 to resolve duplicate class issues
    implementation("com.halilibo.compose-richtext:richtext-commonmark:0.16.0") {
        exclude(group = "com.atlassian.commonmark")
    }
    implementation("com.halilibo.compose-richtext:richtext-ui-material3:0.16.0")
    implementation("org.commonmark:commonmark:0.21.0")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation(platform("androidx.compose:compose-bom:2024.10.00"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
