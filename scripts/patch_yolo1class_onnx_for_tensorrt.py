#!/usr/bin/env python3
"""Patch a 1-class YOLO ONNX export for TensorRT 8.x.

TensorRT 8.2 on Jetson Nano cannot import ONNX `Mod`. Ultralytics' 1-class
NMS-style export uses `Mod(topk_index, 1)` to compute class IDs, which is
always zero. This script replaces that specific `Mod(x, 1)` node with
`Sub(x, x)`, preserving the tensor shape/type while avoiding an unsupported op.

Run this after exporting ONNX and before `trtexec`:

    python3 scripts/patch_yolo1class_onnx_for_tensorrt.py \
      models/exp.onnx models/exp_trt_ready.onnx
"""
from __future__ import print_function

import argparse
from pathlib import Path


def patch_onnx(input_path, output_path):
    try:
        import onnx
    except Exception as exc:  # pragma: no cover - environment-specific
        raise SystemExit(
            "This script requires the optional `onnx` Python package. "
            "Run it in the export environment that has onnx installed, or install onnx there. "
            "Original import error: %s" % exc
        )

    model = onnx.load(str(input_path))
    constants = _constant_values_by_output(onnx, model)
    patched = 0
    skipped_mods = 0
    for node in model.graph.node:
        if node.op_type != "Mod":
            continue
        if len(node.input) < 2 or not _is_scalar_one(constants.get(node.input[1])):
            skipped_mods += 1
            continue
        # In the current 1-class YOLO face export this is Mod(topk_index, 1).
        # Replacing it with Sub(topk_index, topk_index) is mathematically
        # equivalent for modulo 1 and keeps output shape/type stable.
        node.op_type = "Sub"
        node.input[:] = [node.input[0], node.input[0]]
        del node.attribute[:]
        patched += 1

    if patched == 0:
        raise SystemExit("No Mod nodes were patched; refusing to write an unchanged TensorRT-ready ONNX.")
    onnx.checker.check_model(model)
    onnx.save(model, str(output_path))
    if skipped_mods:
        print("skipped %d Mod node(s) whose divisor was not a scalar 1" % skipped_mods)
    return patched


def _constant_values_by_output(onnx, model):
    values = {}
    for initializer in model.graph.initializer:
        values[initializer.name] = onnx.numpy_helper.to_array(initializer)
    for node in model.graph.node:
        if node.op_type != "Constant" or len(node.output) != 1:
            continue
        for attr in node.attribute:
            if attr.name == "value":
                values[node.output[0]] = onnx.numpy_helper.to_array(attr.t)
                break
    return values


def _is_scalar_one(value):
    if value is None:
        return False
    try:
        return value.size == 1 and int(value.reshape(-1)[0]) == 1
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Patch 1-class YOLO ONNX Mod nodes for TensorRT 8.x")
    parser.add_argument("input", type=Path, help="Input ONNX path")
    parser.add_argument("output", type=Path, help="Output TensorRT-ready ONNX path")
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit("Input ONNX does not exist: %s" % args.input)
    patched = patch_onnx(args.input, args.output)
    print("patched %d Mod node(s): %s -> %s" % (patched, args.input, args.output))


if __name__ == "__main__":
    main()
