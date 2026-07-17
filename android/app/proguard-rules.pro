# Kotlin serialization generates serializers at compile time. Keep model metadata used by JSON import/export.
-keepattributes *Annotation*,InnerClasses,EnclosingMethod
-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
}
-if @kotlinx.serialization.Serializable class ** {
    static **$* *;
}
-keepclasseswithmembers class ** {
    kotlinx.serialization.KSerializer serializer(...);
}
