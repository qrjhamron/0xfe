#!/bin/sh
# Build the pinned Patricia engine for Android arm64 and stage it where
# Gradle packages native libraries.
#
# The engine is compiled with the Android NDK (bionic libc) whenever
# ANDROID_NDK_HOME/ANDROID_NDK_ROOT is set, which is how GitHub Actions
# builds it: a bionic binary runs natively inside the app sandbox. Without
# an NDK it falls back to a fully static glibc cross build for local use.
set -eu

PIN=67d83d7056801cfab868872d27b99d192488a316
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC="$ROOT/.patricia-src"
JNILIBS="$ROOT/app/src/main/jniLibs"
BIN="$SRC/engine/patricia_aarch64"

if [ ! -d "$SRC/engine" ]; then
    rm -rf "$SRC"
    mkdir -p "$SRC"
    curl -fsSL "https://github.com/Adam-Kulju/Patricia/archive/$PIN.tar.gz" \
        | tar -xz -C "$SRC" --strip-components=1
fi

NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
if [ -n "$NDK" ]; then
    CLANGXX=$(find "$NDK/toolchains/llvm/prebuilt" -name clang++ -path '*/bin/*' 2>/dev/null | head -n 1)
    STRIP=$(find "$NDK/toolchains/llvm/prebuilt" -name llvm-strip -path '*/bin/*' 2>/dev/null | head -n 1)
    if [ -z "$CLANGXX" ] || [ -z "$STRIP" ]; then
        echo "NDK LLVM toolchain incomplete under $NDK" >&2
        exit 1
    fi
    cd "$SRC/engine"
    # API 26 matches the app minSdk. -static-libstdc++ keeps libc++ inside
    # the executable so nothing else must ship beside it. arm64-v8a is for
    # phones; x86_64 lets the same APK run in PC emulators for testing.
    build_abi() {
        "$CLANGXX" --target="$1" -O3 -std=c++20 -ffast-math "$3" \
            -pthread -static-libstdc++ \
            src/patricia.cpp src/fathom/src/tbprobe.c -o patricia_bin
        "$STRIP" patricia_bin
        mkdir -p "$JNILIBS/$2"
        cp patricia_bin "$JNILIBS/$2/libpatricia.so"
        chmod 755 "$JNILIBS/$2/libpatricia.so"
        echo "Staged $JNILIBS/$2/libpatricia.so"
    }
    build_abi aarch64-linux-android26 arm64-v8a -march=armv8-a
    build_abi x86_64-linux-android26 x86_64 -march=x86-64-v3
    exit 0
else
    cd "$SRC/engine"
    make cross-aarch64 CROSS="${CROSS:-aarch64-linux-gnu}"
    if command -v "${CROSS:-aarch64-linux-gnu}-strip" >/dev/null 2>&1; then
        "${CROSS:-aarch64-linux-gnu}-strip" patricia_aarch64
    fi
fi

mkdir -p "$JNILIBS/arm64-v8a"
cp "$BIN" "$JNILIBS/arm64-v8a/libpatricia.so"
chmod 755 "$JNILIBS/arm64-v8a/libpatricia.so"
echo "Staged $JNILIBS/arm64-v8a/libpatricia.so"
