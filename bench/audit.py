"""Audit public Indian-law datasets used to fine-tune legal chatbots -> bench/out/audit.json

For each dataset, every training example is scanned with sanhita's citation finder.
An example "teaches repealed law as current" if it cites an IPC / CrPC / Evidence Act
section and never mentions the 2023 codes or the repeal.
Also: how the Supreme Court's own citations moved from old to new codes, by year.
"""
import json
import os
import re
import sys
import urllib.request
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sanhita.cite import find_citations  # noqa: E402
from sanhita.check import heading  # noqa: E402

SFT = os.path.expanduser("~/Downloads/claude/rawdata2/law/sft/")
OLD, NEW = {"IPC", "CRPC", "IEA"}, {"BNS", "BNSS", "BSA"}
AWARE = re.compile(r"bharatiya|\bbns\b|\bbnss\b|\bbsa\b|repeal|replaced|2023 code|new criminal law", re.I)


def downloads(repo):
    try:
        return json.load(urllib.request.urlopen(f"https://huggingface.co/api/datasets/{repo}")).get("downloads")
    except Exception:
        return None


def load():
    sets = {}
    j = pd.concat([pd.read_csv(SFT + f"jizzu__llama2_indian_law_v2__{s}.csv") for s in ("train", "validation", "test")])
    sets["jizzu/llama2_indian_law_v2"] = j.text.tolist()
    v = json.load(open(SFT + "viber1__indian-law-dataset__train.jsonl"))
    sets["viber1/indian-law-dataset"] = [x.get("Instruction", "") + "\n" + x.get("Response", "") for x in v]
    s = pd.read_json(SFT + "shruths204__basic-legal-qa-india__synthetic_legal_qna_dataset.json")
    sets["shruths204/basic-legal-qa-india"] = (s.question + "\n" + s.answer).tolist()
    n = pd.concat([pd.read_json(SFT + f, lines=True) for f in os.listdir(SFT) if f.startswith("nisaar__")])
    sets["nisaar/Lawyer_GPT_India"] = (n.question + "\n" + n.answer).tolist()
    m = pd.read_parquet(SFT + "Mukesh555__indian_lawyer_dataset__train-00000-of-00001.parquet")
    sets["Mukesh555/indian_lawyer_dataset"] = (m.instruction + "\n" + m.output).tolist()
    b = pd.read_parquet(SFT + "Akshatpunia0912__Indian-Laws__indian_law_bare_acts_dataset.parquet")
    sets["Akshatpunia0912/Indian-Laws (+3 identical copies)"] = b.law.tolist()
    g = pd.concat([pd.read_json(SFT + f, lines=True) for f in os.listdir(SFT)
                   if f.startswith("GSMS-B__Indian-Legal-QA") and "combined" in f])
    sets["GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA (new-law control)"] = (g.question + "\n" + g.answer).tolist()
    return sets, b


def main():
    sets, bare = load()
    out = {"datasets": {}}
    dl_ids = {"jizzu/llama2_indian_law_v2": ["jizzu/llama2_indian_law_v2"],
              "viber1/indian-law-dataset": ["viber1/indian-law-dataset"],
              "shruths204/basic-legal-qa-india": ["shruths204/basic-legal-qa-india"],
              "nisaar/Lawyer_GPT_India": ["nisaar/Lawyer_GPT_India"],
              "Mukesh555/indian_lawyer_dataset": ["Mukesh555/indian_lawyer_dataset"],
              "Akshatpunia0912/Indian-Laws (+3 identical copies)": ["Akshatpunia0912/Indian-Laws", "Vikaschou/Indian-Laws",
                                                                    "mratanusarkar/Indian-Laws", "manjot007/Indian-Laws"],
              "GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA (new-law control)": ["GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA"]}
    for name, texts in sets.items():
        n = len(texts)
        cite_any = cite_old = cite_new = stale = 0
        top = Counter()
        for t in texts:
            t = str(t)
            cs = find_citations(t, infer_act=False)
            acts = {c.act for c in cs if c.act}
            if not acts & (OLD | NEW):
                continue
            cite_any += 1
            if acts & OLD:
                cite_old += 1
            if acts & NEW:
                cite_new += 1
            if acts & OLD and not acts & NEW and not AWARE.search(t):
                stale += 1
                top.update(f"{c.act}:{c.section}" for c in cs if c.act in OLD)
        out["datasets"][name] = {
            "examples": n, "cite_criminal_code": cite_any, "cite_old": cite_old, "cite_new": cite_new,
            "teach_repealed_as_current": stale,
            "share_of_citing_examples_stale": round(stale / cite_any, 4) if cite_any else None,
            "downloads": sum(filter(None, (downloads(r) for r in dl_ids[name]))),
            "top_stale_sections": [{"id": k, "n": v, "heading": heading(k)} for k, v in top.most_common(8)],
        }
        print(f"{name:55s} n={n:6d} cite={cite_any:5d} old={cite_old:5d} new={cite_new:5d} stale={stale:5d}")
    acts = Counter(bare.act_title)
    out["bare_acts_dataset"] = {
        "acts": len(acts),
        "has_ipc": any("Penal Code" in a for a in acts), "has_crpc": any("Criminal Procedure" in a for a in acts),
        "has_evidence_act": any("Evidence Act" in a for a in acts),
        "has_bns": any("Nyaya" in a for a in acts), "has_bnss": any("Nagarik" in a for a in acts),
        "has_bsa": any("Sakshya" in a for a in acts),
    }
    print(out["bare_acts_dataset"])
    # Supreme Court citations by year (Dhara)
    P = SFT + "AravArun__dhara-indian-criminal-law__"
    cit = pd.read_parquet(P + "citations.parquet")
    jd = pd.read_parquet(P + "judgments.parquet")[["id", "decided_on"]]
    cit = cit.merge(jd, left_on="judgment_id", right_on="id")
    cit["year"] = cit.decided_on.str[:4].astype(int)
    cit["grp"] = cit.act.map(lambda a: "new" if a in NEW else "old")
    yr = cit[cit.year >= 2015].groupby(["year", "grp"]).size().unstack(fill_value=0)
    out["supreme_court_by_year"] = {int(y): {"old": int(r.get("old", 0)), "new": int(r.get("new", 0))}
                                    for y, r in yr.iterrows()}
    # judgments in 2025-26 that cite a new code
    rec = cit[cit.year >= 2025]
    out["sc_2025_26"] = {"judgments": int(rec.judgment_id.nunique()),
                         "citing_new_code": int(rec[rec.grp == "new"].judgment_id.nunique())}
    print(out["supreme_court_by_year"], out["sc_2025_26"])
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "out", "audit.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
