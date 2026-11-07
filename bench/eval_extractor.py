"""Evaluate the citation extractor on real Supreme Court citation strings.

Dhara's citations.parquet has 159,686 section references found in 9,686 Supreme Court
judgments, each with its raw text and the resolved provision. Grouping rows by raw
string gives a gold set of (act, section) per string. We report micro precision /
recall / F1 on sections (act + number), and on numbers alone.
"""
import json
import os
import random
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sanhita.cite import find_citations  # noqa: E402

RAW = os.path.expanduser("~/Downloads/claude/rawdata2/law/sft/AravArun__dhara-indian-criminal-law__citations.parquet")


def main():
    c = pd.read_parquet(RAW)
    c["gold"] = c.provision_id.str.upper()
    g = c.groupby(["chunk_id", "raw"]).gold.agg(lambda s: set(s)).reset_index()
    print("unique (chunk, raw) strings:", len(g))
    tp = fp = fn = 0
    tpn = fpn = fnn = 0
    errors = []
    by_act = Counter()
    for raw, gold in zip(g.raw, g.gold):
        pred = {f"{x.act}:{x.section}" for x in find_citations(raw) if x.act}
        gold = {x.split("(")[0] for x in gold}
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)
        pn = {p.split(":")[1] for p in pred}
        gn = {x.split(":")[1] for x in gold}
        tpn += len(pn & gn); fpn += len(pn - gn); fnn += len(gn - pn)
        for x in gold:
            by_act[(x.split(":")[0], x in pred)] += 1
        if pred != gold and len(errors) < 4000:
            errors.append({"raw": raw, "gold": sorted(gold), "pred": sorted(pred)})
    p, r = tp / (tp + fp), tp / (tp + fn)
    res = {"strings": len(g), "precision": p, "recall": r, "f1": 2 * p * r / (p + r),
           "number_only": {"precision": tpn / (tpn + fpn), "recall": tpn / (tpn + fnn)},
           "recall_by_act": {a: by_act[(a, True)] / (by_act[(a, True)] + by_act[(a, False)])
                             for a in sorted({k[0] for k in by_act})}}
    print(json.dumps(res, indent=1))
    random.Random(0).shuffle(errors)
    res["error_sample"] = errors[:40]
    json.dump(res, open(os.path.join(os.path.dirname(__file__), "out", "extractor_eval.json"), "w"), indent=1,
              ensure_ascii=False)
    for e in errors[:25]:
        print(e)


if __name__ == "__main__":
    main()
