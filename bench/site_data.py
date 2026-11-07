"""Merge all results into docs/data/report.json (what the website renders)."""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bench.score import META, classify, STOP  # noqa: E402
from sanhita.check import heading, LABEL  # noqa: E402

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
DOCS = os.path.join(HERE, "..", "docs", "data")
LABELS = {"gemma-3-1b-it": "Gemma 3 · 1B", "qwen3-1.7b": "Qwen3 · 1.7B", "llama-3.2-3b-instruct": "Llama 3.2 · 3B",
          "phi-4-mini-instruct": "Phi-4 mini · 3.8B", "gemma-3-4b-it": "Gemma 3 · 4B", "qwen3-4b": "Qwen3 · 4B",
          "qwen3-8b": "Qwen3 · 8B", "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
          "qwen3-1.7b+lora-adapters-qwen3-1.7b": "Qwen3 1.7B + our LoRA"}
FAMOUS = ["IPC:302", "IPC:420", "IPC:376", "IPC:498A", "IPC:307", "IPC:354", "IPC:379", "IPC:506", "IPC:326A", "IPC:323", "CRPC:154", "CRPC:438", "IEA:65B"]


def lab(sid):
    a, n = sid.split(":")
    return f"{LABEL[a]} {n}"


REFUSE = re.compile(r"I can'?t provide|I cannot provide|illegal or harmful|I can'?t help|I'?m not able to provide|"
                    r"don'?t have access to a search engine|cannot verify", re.I)


def load_raw(name):
    return {json.loads(l)["id"]: STOP.split(json.loads(l)["output"] or "", 1)[0].strip()
            for l in open(os.path.join(OUT, "raw", name + ".jsonl"), encoding="utf-8")}


def refusals(names):
    out = {}
    for n in names:
        o = load_raw(n)
        ids = [k for k in o if META.get(k, {}).get("task") in ("scenario", "current")]
        out[n] = sum(bool(REFUSE.search(o[k])) for k in ids) / max(1, len(ids))
    return out


def quotes(names):
    """Three real answers: a confident repealed-law answer for a 2025 incident, a refusal, a carry-over."""
    picks = []
    raw = {n: load_raw(n) for n in names}
    def first(pred, pref):
        for n in pref:
            for pid, out in raw[n].items():
                m = META.get(pid)
                if m and pred(m, out):
                    return n, pid, m, out
        return None
    hit = first(lambda m, o: m["task"] == "scenario" and classify(m, o) == "stale" and m["old"] in FAMOUS and 40 < len(o) < 400,
                ["qwen3-8b", "qwen3-1.7b", "phi-4-mini-instruct"])
    if hit:
        n, pid, m, o = hit
        picks.append({"model": LABELS[n], "q": "an incident in 2025: " + heading(m["old"]).lower(), "a": " ".join(o.split())[:240],
                      "truth": f"For a 2025 offence the law is {', '.join(lab(g) for g in m['gold'])}; {lab(m['old'])} was repealed."})
    hit = first(lambda m, o: m["task"] == "scenario" and REFUSE.search(o) and "harmful" in o, ["llama-3.2-3b-instruct", "phi-4-mini-instruct"])
    if hit:
        n, pid, m, o = hit
        picks.append({"model": LABELS[n], "q": "which law covers this? (" + heading(m["old"]).lower() + ")", "a": " ".join(o.split())[:200],
                      "truth": f"A refusal. The answer is {', '.join(lab(g) for g in m['gold'])}: basic legal information."})
    hit = first(lambda m, o: m["task"] == "convert" and classify(m, o) == "carryover" and m["old"] in FAMOUS,
                ["qwen3-1.7b", "gemma-3-1b-it", "phi-4-mini-instruct", "qwen3-8b"])
    if hit:
        n, pid, m, o = hit
        trap = f"{m['new_act']}:{m['old'].split(':')[1]}"
        picks.append({"model": LABELS[n], "q": f"{lab(m['old'])} ({heading(m['old'])}) is which section now?", "a": " ".join(o.split())[:120],
                      "truth": f"{lab(trap)} is '{heading(trap)}'. The answer is {', '.join(lab(g) for g in m['gold'])}." if heading(trap)
                      else f"There is no {lab(trap)} (the {LABEL[m['new_act']]} has fewer sections). The answer is {', '.join(lab(g) for g in m['gold'])}."})
    return picks


def main():
    llm = json.load(open(os.path.join(OUT, "llm_report.json")))
    audit = json.load(open(os.path.join(OUT, "audit.json")))
    ext = json.load(open(os.path.join(OUT, "extractor_eval.json")))
    lora = json.load(open(os.path.join(OUT, "lora_report.json"))) if os.path.exists(os.path.join(OUT, "lora_report.json")) else None
    models = [{"name": k, "label": LABELS.get(k, k), "tasks": v["tasks"]} for k, v in llm.items()]
    base = [m for m in models if "lora" not in m["name"]]
    cur = [m["tasks"]["current"] for m in base if "current" in m["tasks"]]
    best = max(base, key=lambda m: m["tasks"].get("current", {}).get("correct", 0))
    stale_avg = sum(c.get("stale", 0) + c.get("carryover", 0) for c in cur) / max(1, len(cur))
    sft = [d for k, d in audit["datasets"].items() if "control" not in k and d["cite_criminal_code"]]
    stale_n = sum(d["teach_repealed_as_current"] for d in sft)
    cite_n = sum(d["cite_criminal_code"] for d in sft)
    tot = sum(m["tasks"]["current"]["n"] for m in base if "current" in m["tasks"])
    ok = sum(round(m["tasks"]["current"].get("correct", 0) * m["tasks"]["current"]["n"]) for m in base if "current" in m["tasks"])
    rr = refusals([m["name"] for m in base])
    worst = max(rr, key=rr.get)
    hero = [
        {"v": f"{ok:,} / {tot:,}", "l": "answers, across 5 models, named the section actually in force today"},
        {"v": f"{stale_avg * 100:.0f}%", "l": "of answers cite a repealed section or an old number on the new code"},
        {"v": f"{stale_n / cite_n * 100:.0f}%", "l": f"of criminal-code citations in public Indian-law fine-tuning sets are pre-2024 ({stale_n:,}/{cite_n:,})"},
        {"v": f"{ext['f1'] * 100:.1f}%", "l": f"citation-parsing F1 on {ext['strings']:,} real Supreme Court strings"},
    ]
    refusal = {"model": LABELS.get(worst, worst), "rate": rr[worst], "all": rr}
    if lora:
        tr = lora["lora"].get("current:trained", {}).get("correct", 0)
        ho = lora["lora"].get("current:heldout", {}).get("correct", 0)
        g = lambda d, k: (d.get(k) or {}).get("correct", 0)
        lora["takeaway"] = (f"600 LoRA steps on 5,805 examples moved old→new conversion from {g(lora['base'], 'convert:trained') * 100:.0f}% to "
                            f"{g(lora['lora'], 'convert:trained') * 100:.0f}% on trained sections and to {g(lora['lora'], 'convert:heldout') * 100:.0f}% on "
                            f"sections it never saw: about the same, so it learned the answer format, not the law. Meanwhile general knowledge "
                            f"(ARC-Easy) fell from {lora['arc_base'] * 100:.0f}% to {lora['arc_lora'] * 100:.0f}% and it stopped placing 2022 offences "
                            f"under the IPC. Retraining a small model is the wrong tool; checking answers against the official table (what sanhita does) is the fix.")
    rep = {"hero": hero, "refusal": refusal, "models": models, "quotes": quotes([m["name"] for m in base]), "lora": lora, "audit": audit,
           "extractor": {k: ext[k] for k in ("strings", "precision", "recall", "f1")},
           "bench_note": (f"740 questions per model, greedy decoding, gold answers from NCRB's correspondence tables; local models ran 4-bit "
                       f"on an Apple M4 (MLX). Gemini could not be included: the free API tier's daily quota was used up by the "
                       f"medicine benchmark. Note the refusals: {refusal['model']} refused {refusal['rate'] * 100:.0f}% of plain-language "
                       f"questions about the law (e.g. a woman asking which law covers an acid attack) as “illegal or harmful activities”.")}
    os.makedirs(DOCS, exist_ok=True)
    json.dump(rep, open(os.path.join(DOCS, "report.json"), "w"), ensure_ascii=False)
    shutil.copy(os.path.join(HERE, "..", "sanhita", "data", "statutes.json"), DOCS)
    print("wrote", os.path.join(DOCS, "report.json"), "| quotes:", len(rep["quotes"]))
    for h in hero:
        print(" ", h["v"], h["l"])


if __name__ == "__main__":
    main()
