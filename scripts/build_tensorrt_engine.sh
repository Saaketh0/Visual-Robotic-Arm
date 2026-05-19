#!/usr/bin/env bash
set -euo pipefail

ONNX_PATH="${1:-/workspace/xarm_ws/models/exp_trt_ready.onnx}"
ENGINE_PATH="${2:-/workspace/xarm_ws/models/exp.engine}"
WORKSPACE_MB="${XARM_TRT_WORKSPACE_MB:-512}"
TRTEXEC="${TRTEXEC:-}"

if [[ -z "$TRTEXEC" ]]; then
  if command -v trtexec >/dev/null 2>&1; then
    TRTEXEC="$(command -v trtexec)"
  elif [[ -x /usr/src/tensorrt/bin/trtexec ]]; then
    TRTEXEC="/usr/src/tensorrt/bin/trtexec"
  else
    echo "ERROR: trtexec not found. Expected it on PATH or at /usr/src/tensorrt/bin/trtexec." >&2
    exit 1
  fi
fi

if [[ ! -f "$ONNX_PATH" ]]; then
  echo "ERROR: ONNX path does not exist: $ONNX_PATH" >&2
  exit 1
fi

mkdir -p "$(dirname "$ENGINE_PATH")"
echo "Building TensorRT engine: $ONNX_PATH -> $ENGINE_PATH"
"$TRTEXEC" \
  --onnx="$ONNX_PATH" \
  --saveEngine="$ENGINE_PATH" \
  --fp16 \
  --workspace="$WORKSPACE_MB" \
  --buildOnly
ls -lh "$ENGINE_PATH"
