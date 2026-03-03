# Keep GSON data models to avoid 422 errors due to field renaming
-keep class com.proteus.ai.api.model.** { *; }

# Also keep the Enum types if any
-keepclassmembers enum com.proteus.ai.api.model.** { *; }

# Keep GSON annotations if needed
-keepattributes Signature, *Annotation*, EnclosingMethod
