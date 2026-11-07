"""Score sanhita benchmark outputs -> bench/out/llm_report.json

Every answer is classified (citations parsed with sanhita.cite):
  correct    cites a gold section of the right new code
  carryover  cites the NEW code with the OLD number (e.g. "BNS 302" for murder)
  stale      cites the repealed code (IPC / CrPC / Evidence Act) and not the gold new section
  wrong      cites the new code with some other number
  none       cites nothing usable
For `temporal`, the gold for a 2022 offence is the OLD section (the IPC still applies).
"""
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sanhita.cite import find_citations  # noqa: E402

HERE = os.path.dirname(__file__)
META = json.load(open(os.path.join(HERE, "tasks_meta.json")))
OLD = {"IPC", "CRPC", "IEA"}
STOP = re.compile(r"<end_of_turn>|<\|im_end\|>|<\|eot_id\|>|<\|end\|>|<\|endoftext\|>|</s>")


def num(sid):
    return sid.split(":")[1]


def classify(m, out):
    gold_nums = {num(g) for g in m["gold"]}
    old_num = num(m["old"])
    if m["task"] == "convert":
        t = re.sub(r"(?i)bharatiya\s+\w+\s+\w+(\s+sanhita)?|20\d\d|19\d\d|1860|1872|1973", " ", out)
        nm = re.search(r"\b(\d{1,3}[A-Z]{0,2})\b", t)
        if not nm:
            return "none"
        n = nm.group(1)
        if n in gold_nums:
            return "correct"
        return "carryover" if n == old_num else "wrong"
    cites = find_citations(out)
    new_act = m["new_act"]
    if m["task"] == "temporal" and m["year"] == 2022:
        if any(c.act == m["old"].split(":")[0] and c.section == old_num for c in cites):
            return "correct"
        if any(c.act == new_act for c in cites):
            return "wrong_code"
        return "wrong" if cites else "none"
    if any(c.act == new_act and c.section in gold_nums for c in cites):
        return "correct"
    if any(c.act == new_act and c.section == old_num for c in cites):
        return "carryover"
    if any(c.act in OLD for c in cites):
        return "stale"
    if any(c.act == new_act for c in cites):
        return "wrong"
    return "none"


def score_model(path):
    res, examples = {}, {}
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        m = META.get(d["id"])
        if not m:
            continue
        out = STOP.split(d["output"] or "", 1)[0]
        c = classify(m, out)
        task = m["task"] + (f"_{m['year']}" if m["task"] == "temporal" else "")
        res.setdefault(task, Counter())[c] += 1
        key = (m["task"], c)
        if c != "correct" and len(examples.setdefault(f"{m['task']}:{c}", [])) < 6:
            examples[f"{m['task']}:{c}"].append({"id": d["id"], "gold": m["gold"], "answer": out.strip()[:220]})
    summary = {}
    for t, cnt in res.items():
        n = sum(cnt.values())
        summary[t] = {"n": n, **{k: round(v / n, 4) for k, v in cnt.items()}}
    return {"tasks": summary, "examples": examples}


def main():
    report = {}
    for p in sorted(glob.glob(os.path.join(HERE, "out", "raw", "*.jsonl"))):
        name = os.path.basename(p)[:-6]
        report[name] = score_model(p)
        line = " | ".join(f"{t} n={v['n']} ok={v.get('correct', 0):.2f} stale={v.get('stale', 0):.2f} "
                          f"carry={v.get('carryover', 0):.2f}" for t, v in sorted(report[name]["tasks"].items()))
        print(f"{name:22s} {line}")
    json.dump(report, open(os.path.join(HERE, "out", "llm_report.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
