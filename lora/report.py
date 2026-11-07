"""Compare base vs LoRA-updated model -> bench/out/lora_report.json

Splits benchmark accuracy into sections the adapter was TRAINED on (asked with new
wording) vs sections it NEVER saw, checks temporal reasoning (a 2022 offence still
belongs under the IPC), and ARC-Easy accuracy as a forgetting check.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bench.score import META, classify, STOP  # noqa: E402

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
HELD = set(json.load(open(os.path.join(HERE, "data", "split.json")))["heldout_sections"])
ARC = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(os.path.join(HERE, "data", "arc_prompts.jsonl"))}


def load(path):
    return {json.loads(l)["id"]: STOP.split(json.loads(l)["output"] or "", 1)[0] for l in open(path, encoding="utf-8")}


def bench(outs):
    agg = {}
    for pid, out in outs.items():
        m = META.get(pid)
        if not m:
            continue
        c = classify(m, out)
        if m["task"] in ("convert", "current", "scenario"):
            key = f"{m['task']}:{'heldout' if m['old'] in HELD else 'trained'}"
        elif m["task"] == "temporal":
            key = f"temporal:{m['year']}"
        else:
            continue
        agg.setdefault(key, []).append(c)
    return {k: {"n": len(v), "correct": round(v.count("correct") / len(v), 4),
                "carryover": round(v.count("carryover") / len(v), 4), "stale": round(v.count("stale") / len(v), 4),
                "wrong_code": round(v.count("wrong_code") / len(v), 4)} for k, v in sorted(agg.items())}


def arc(path):
    o = load(path)
    ok = [bool(re.search(r"\b([A-E1-5])\b", v[:20])) and re.search(r"\b([A-E1-5])\b", v[:20]).group(1) == ARC[k]
          for k, v in o.items() if k in ARC]
    return round(sum(ok) / len(ok), 4) if ok else None


def main():
    base = os.path.join(ROOT, "bench", "out", "raw", "qwen3-1.7b.jsonl")
    lora = os.path.join(ROOT, "bench", "out", "raw", "qwen3-1.7b+lora-adapters-qwen3-1.7b.jsonl")
    rep = {"base": bench(load(base)), "lora": bench(load(lora)),
           "arc_base": arc(os.path.join(HERE, "out", "qwen3-1.7b.jsonl")),
           "arc_lora": arc(os.path.join(HERE, "out", "qwen3-1.7b+lora-adapters-qwen3-1.7b.jsonl")),
           "heldout_sections": len(HELD)}
    for k in sorted(set(rep["base"]) | set(rep["lora"])):
        b, l = rep["base"].get(k, {}), rep["lora"].get(k, {})
        print(f"{k:22s} base {b.get('correct')} -> lora {l.get('correct')}  (n={l.get('n')})")
    print("ARC-Easy", rep["arc_base"], "->", rep["arc_lora"])
    json.dump(rep, open(os.path.join(ROOT, "bench", "out", "lora_report.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
