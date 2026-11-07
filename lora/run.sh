#!/usr/bin/env bash
# LoRA knowledge update: teach Qwen3-1.7B the IPC/CrPC/IEA -> BNS/BNSS/BSA mapping
# (80% of sections), then evaluate on the benchmark prompts + an ARC forgetting check.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=mlx-community/Qwen3-1.7B-4bit
AD=lora/adapters-qwen3-1.7b
python lora/make_data.py
python -m mlx_lm lora --model "$BASE" --train --data lora/data --iters 600 --batch-size 8 \
  --num-layers 16 --learning-rate 1e-4 --mask-prompt --max-seq-length 256 \
  --steps-per-eval 250 --val-batches 15 --save-every 300 --adapter-path "$AD" 2>&1 | tee lora/train.log
# benchmark prompts with the adapter, plus ARC-Easy for base and adapter
python bench/llm.py bench/prompts.jsonl bench/out/raw "$BASE@@$AD"
python bench/llm.py lora/data/arc_prompts.jsonl lora/out "$BASE" "$BASE@@$AD"
python lora/report.py
