"""Capture real chain-of-thought traces from small open models (MLX, local).

Usage:
  python3 gen.py --model mlx-community/Qwen3-1.7B-4bit --mode think --seeds 0 1 2 --out runs/qwen3_think.jsonl

Each line of the output file is one generation: the exact prompt, the sampling
settings, the seed, the full raw output, the thinking part, the answer part,
and token counts. Nothing is edited after the model writes it.
"""
import argparse
import datetime
import glob
import json
import os
import platform
import time

import mlx.core as mx
import mlx_lm
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

HERE = os.path.dirname(os.path.abspath(__file__))


def snapshot_hash(repo):
    pat = os.path.expanduser(
        "~/.cache/huggingface/hub/models--%s/snapshots/*/" % repo.replace("/", "--"))
    hits = glob.glob(pat)
    return os.path.basename(os.path.normpath(hits[0])) if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=["think", "nothink"], default="think")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--max_tokens", type=int, default=8192)
    ap.add_argument("--temp", type=float, default=0.6)
    ap.add_argument("--top_p", type=float, default=0.95)
    ap.add_argument("--top_k", type=int, default=0)
    ap.add_argument("--questions", default=os.path.join(HERE, "questions.json"))
    ap.add_argument("--only", nargs="*", default=None, help="question ids to run")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    questions = json.load(open(args.questions))
    if args.only:
        questions = [q for q in questions if q["id"] in args.only]

    model, tok = load(args.model)
    hf = tok._tokenizer if hasattr(tok, "_tokenizer") else tok
    think_open = hf.convert_tokens_to_ids("<think>")
    think_close = hf.convert_tokens_to_ids("</think>")
    sampler = make_sampler(temp=args.temp, top_p=args.top_p, top_k=args.top_k)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a") as f:
        for q in questions:
            for seed in args.seeds:
                msgs = [{"role": "user", "content": q["text"]}]
                kw = {}
                if "Qwen3" in args.model:
                    kw["enable_thinking"] = (args.mode == "think")
                prompt_text = hf.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=True, **kw)
                prompt_ids = hf.apply_chat_template(
                    msgs, tokenize=True, add_generation_prompt=True, **kw)
                if not isinstance(prompt_ids, list):  # newer transformers return BatchEncoding
                    prompt_ids = list(prompt_ids["input_ids"])
                assert hf.decode(prompt_ids) == prompt_text, "prompt ids do not round-trip"
                mx.random.seed(seed)
                ids = []
                last = None
                t0 = time.time()
                for r in stream_generate(model, tok, prompt_ids,
                                         max_tokens=args.max_tokens, sampler=sampler):
                    ids.append(int(r.token))
                    last = r
                wall = time.time() - t0
                # The final response's token is the stop token when generation ended
                # on EOS; stream_generate does not yield EOS itself, so ids are text only.
                gen_ids = list(ids)
                eos_ids = set(tok.eos_token_ids)
                while gen_ids and gen_ids[-1] in eos_ids:  # final response repeats the stop token
                    gen_ids = gen_ids[:-1]
                if gen_ids and gen_ids[0] == think_open:
                    gen_ids = gen_ids[1:]
                if args.mode == "think":
                    if think_close in gen_ids:
                        k = gen_ids.index(think_close)
                        thinking_ids, answer_ids, closed = gen_ids[:k], gen_ids[k + 1:], True
                    else:
                        thinking_ids, answer_ids, closed = gen_ids, [], False
                else:
                    thinking_ids, answer_ids, closed = [], gen_ids, True
                rec = {
                    "qid": q["id"], "kind": q["kind"], "question": q["text"], "gold": q["gold"],
                    "model": args.model, "snapshot": snapshot_hash(args.model), "mode": args.mode,
                    "seed": seed, "temp": args.temp, "top_p": args.top_p, "top_k": args.top_k,
                    "max_tokens": args.max_tokens, "prompt_text": prompt_text,
                    "raw_output": hf.decode(ids, skip_special_tokens=False),
                    "n_generated_incl_stop": len(ids),
                    "thinking": hf.decode(thinking_ids, skip_special_tokens=False),
                    "answer": hf.decode(answer_ids, skip_special_tokens=False),
                    "n_generated": len(gen_ids), "n_thinking": len(thinking_ids),
                    "n_answer": len(answer_ids), "think_closed": closed,
                    "finish_reason": getattr(last, "finish_reason", None),
                    "generation_tps": round(getattr(last, "generation_tps", 0.0), 1),
                    "peak_memory_gb": round(getattr(last, "peak_memory", 0.0), 2),
                    "wall_seconds": round(wall, 1),
                    "mlx_lm": mlx_lm.__version__, "mlx": mx.__version__,
                    "machine": platform.machine() + " " + platform.mac_ver()[0],
                    "time": datetime.datetime.now().isoformat(timespec="seconds"),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                print("%s seed=%d mode=%s gen=%d think=%d closed=%s %.1fs %s tok/s" % (
                    q["id"], seed, args.mode, len(ids), len(thinking_ids), closed, wall,
                    rec["generation_tps"]), flush=True)


if __name__ == "__main__":
    main()
