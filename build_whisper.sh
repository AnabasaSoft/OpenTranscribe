#!/usr/bin/env bash
# Compila un whisper-cli portable en binaries_linux/whisper-cli.
#
# Lo usa el workflow de CI y sirve igual en local. El binario resultante:
#  - lleva whisper y ggml enlazados estáticamente (sin libwhisper.so/libggml*.so
#    ni RUNPATH apuntando a la carpeta de compilación);
#  - lleva libstdc++ y libgcc estáticas y no usa OpenMP (no depende de libgomp);
#  - no usa -march=native: se compila para x86-64 con AVX2/FMA/F16C, que tiene
#    cualquier CPU de escritorio desde ~2013-2015, en vez de para la CPU de quien compila.
# Solo depende de glibc, así que hay que compilarlo en la distro MÁS ANTIGUA que se
# quiera soportar (el CI usa ubuntu-22.04, glibc 2.35).
set -euo pipefail

WHISPER_VERSION="${WHISPER_VERSION:-v1.8.7}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/.whisper-build/whisper.cpp-$WHISPER_VERSION"
BUILD="$SRC/build-static"
OUT="$ROOT/binaries_linux/whisper-cli"

if [ ! -d "$SRC" ]; then
    git clone --depth 1 --branch "$WHISPER_VERSION" https://github.com/ggerganov/whisper.cpp.git "$SRC"
fi

cmake -S "$SRC" -B "$BUILD" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_NATIVE=OFF \
    -DGGML_OPENMP=OFF \
    -DWHISPER_BUILD_TESTS=OFF \
    -DWHISPER_BUILD_SERVER=OFF \
    -DCMAKE_EXE_LINKER_FLAGS="-static-libstdc++ -static-libgcc"

cmake --build "$BUILD" --target whisper-cli -j "$(nproc)"

mkdir -p "$(dirname "$OUT")"
install -m 755 "$BUILD/bin/whisper-cli" "$OUT"
strip "$OUT"

echo
echo "== $OUT ($WHISPER_VERSION)"
# Comprobaciones: solo bibliotecas del sistema base y sin RUNPATH
NEEDED="$(readelf -d "$OUT" | grep NEEDED | grep -oE '\[[^]]+\]' | tr -d '[]' | tr '\n' ' ')"
echo "Bibliotecas: $NEEDED"
echo "glibc mínima: $(objdump -T "$OUT" | grep -oE 'GLIBC_[0-9.]+' | sort -Vu | tail -1)"
for lib in $NEEDED; do
    case "$lib" in
        libc.so.*|libm.so.*|ld-linux*|libpthread.so.*|libdl.so.*) ;;
        *) echo "ERROR: dependencia no portable: $lib" >&2; exit 1 ;;
    esac
done
if readelf -d "$OUT" | grep -qE 'RPATH|RUNPATH'; then
    echo "ERROR: el binario tiene RPATH/RUNPATH" >&2; exit 1
fi
echo "OK: binario portable"
