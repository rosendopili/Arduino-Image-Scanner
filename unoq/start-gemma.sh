#!/bin/sh
# Start the local Gemma server on the Uno Q. The viewscreen calls it on localhost.

set -eu

MODEL="${MODEL:-/home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf}"
MMPROJ="${MMPROJ:-/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/home/arduino/llama.cpp/build/bin/llama-server}"

LIB_DIR=$(CDPATH= cd -- "$(dirname "$LLAMA_SERVER")" && pwd)
cd "$LIB_DIR"
exec env LD_LIBRARY_PATH="$LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  "$LLAMA_SERVER" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --no-mmproj-offload \
  --image-min-tokens 16 \
  --image-max-tokens 64 \
  --host 127.0.0.1 \
  --port 8080 \
  -c 768 \
  -n 40 \
  -t 4 \
  -rea off
