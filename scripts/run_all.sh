#!/bin/bash
# Runs every capture, one model at a time. Run from the repo root on a Mac with Apple silicon.
python3 scripts/gen.py --model mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit --mode think --seeds 0 1 2 --temp 0.6 --top_p 0.95 --top_k 0 --max_tokens 8192 --out runs/r1distill15_think.jsonl
python3 scripts/gen.py --model mlx-community/Qwen3-1.7B-4bit --mode think --seeds 0 1 2 --temp 0.6 --top_p 0.95 --top_k 20 --max_tokens 8192 --out runs/qwen3_17_think.jsonl
python3 scripts/gen.py --model mlx-community/Qwen3-1.7B-4bit --mode nothink --seeds 0 1 2 --temp 0.6 --top_p 0.95 --top_k 20 --max_tokens 8192 --out runs/qwen3_17_nothink.jsonl
python3 scripts/analyze.py --site .
