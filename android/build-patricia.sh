#!/bin/sh
# Build the pinned Patricia engine as a fully static arm64 binary and stage
# it where Gradle packages native libraries. Run by GitHub Actions; locally
# it needs an aarch64-linux-gnu C++ cross compiler.
set -eu

PIN=67d83d7056801cfab868872d27b99d192488a316
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC="$ROOT/.patricia-src"
OUT="$ROOT/app/src/main/jniLibs/arm64-v8a"

if [ ! -d "$SRC/engine" ]; then
    rm -rf "$SRC"
    mkdir -p "$SRC"
    curl -fsSL "https://github.com/Adam-Kulju/Patricia/archive/$PIN.tar.gz" \
        | tar -xz -C "$SRC" --strip-components=1
fi

cd "$SRC/engine"
make cross-aarch64 CROSS="${CROSS:-aarch64-linux-gnu}"

# Stripping debug/symbol data keeps the APK smaller and the engine faster
# to load; the binary is fully static either way.
if command -v "${CROSS:-aarch64-linux-gnu}-strip" >/dev/null 2>&1; then
    "${CROSS:-aarch64-linux-gnu}-strip" patricia_aarch64
fi

mkdir -p "$OUT"
cp patricia_aarch64 "$OUT/libpatricia.so"
chmod 755 "$OUT/libpatricia.so"
echo "Staged $OUT/libpatricia.so"
