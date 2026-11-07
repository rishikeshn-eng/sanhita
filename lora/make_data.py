"""Build LoRA fine-tuning data that teaches the IPC/CrPC/IEA -> BNS/BNSS/BSA mapping.

Sections are split 80/20 by a hash of the old section id. Training uses ONLY the 80%
and only phrasings that differ from the benchmark's, so evaluation on the benchmark
prompts measures (a) recall of trained sections under new wording and (b) transfer
to sections never trained on. Also trains "what does BNS <n> cover" so the model
learns new numbers' meanings (the carry-over trap), and a few temporal examples.
"""
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sanhita.check import statutes, heading, LABEL  # noqa: E402

HERE = os.path.dirname(__file__)
rng = random.Random(5)
d = statutes()
FULL = {k: v["name"] for k, v in d["acts"].items()}


def split_of(sid):
    return "train" if int(hashlib.md5(sid.encode()).hexdigest(), 16) % 100 < 80 else "heldout"


def lab(sid):
    a, n = sid.split(":")
    return f"{LABEL[a]} {n}"


def main():
    rows, heldout = [], []
    for sid, succ in d["old_to_new"].items():
        tos = [s["to"] for s in succ if s.get("to")]
        if not heading(sid):
            continue
        sp = split_of(sid)
        if sp == "heldout":
            heldout.append(sid)
            continue
        a, n = sid.split(":")
        if not tos:
            ans = f"{lab(sid)} ({heading(sid)}) was repealed on 1 July 2024 and has no equivalent in the {LABEL[d['acts'][a]['successor']]}."
            qs = [f"What replaced {lab(sid)}?", f"{lab(sid)} ka naya section kya hai?"]
            rows += [(q, ans) for q in qs]
            continue
        new = " and ".join(f"{lab(t)} ({heading(t)})" for t in tos)
        rows += [
            (f"{lab(sid)} is now which section?", f"{new}. {lab(sid)} was repealed on 1 July 2024."),
            (f"What is the new section number for {lab(sid)} ({heading(sid)}) under the 2023 criminal laws?", f"{new}."),
            (f"{lab(sid)} ka naya section kaunsa hai?", f"{new}."),
            (f"Which provision now covers '{heading(sid)}'?", f"{new} (formerly {lab(sid)})."),
        ]
        for t in tos:
            rows.append((f"What does {lab(t)} deal with?", f"{lab(t)} deals with: {heading(t)}. It replaced {lab(sid)}."))
        trap = f"{d['acts'][a]['successor']}:{n}"
        if heading(trap) and trap not in tos:
            rows.append((f"Is {lab(trap)} the same as {lab(sid)}?",
                         f"No. {lab(trap)} is '{heading(trap)}'. {lab(sid)} ('{heading(sid)}') is now {new}."))
        if rng.random() < 0.15:
            rows.append((f"An offence under {lab(sid)} was committed in 2021 and is being tried now. Which section applies?",
                         f"{lab(sid)}: offences committed before 1 July 2024 are tried under the old code."))
    rng.shuffle(rows)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    n_val = 150
    for name, part in (("valid", rows[:n_val]), ("train", rows[n_val:])):
        with open(os.path.join(HERE, "data", f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for q, a in part:
                f.write(json.dumps({"messages": [{"role": "user", "content": q}, {"role": "assistant", "content": a}]},
                                   ensure_ascii=False) + "\n")
    json.dump({"heldout_sections": sorted(heldout)}, open(os.path.join(HERE, "data", "split.json"), "w"))
    print(len(rows), "examples;", len(heldout), "held-out old sections")


if __name__ == "__main__":
    main()
