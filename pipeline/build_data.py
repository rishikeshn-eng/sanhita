"""Build sanhita/data/statutes.json from the Dhara dataset (CC-BY-4.0).

Dhara (AravArun/dhara-indian-criminal-law) packages all six codes and NCRB's official
old-to-new correspondence tables. We keep, for every section of IPC / CrPC / IEA /
BNS / BNSS / BSA: heading, chapter and a text excerpt, plus the mapping both ways.
"""
import json
import os

import pandas as pd

RAW = os.path.expanduser("~/Downloads/claude/rawdata2/law/sft/AravArun__dhara-indian-criminal-law__")
OUT = os.path.join(os.path.dirname(__file__), "..", "sanhita", "data", "statutes.json")

ACTS = {
    "IPC": {"name": "Indian Penal Code, 1860", "repealed": True, "successor": "BNS"},
    "CRPC": {"name": "Code of Criminal Procedure, 1973", "repealed": True, "successor": "BNSS"},
    "IEA": {"name": "Indian Evidence Act, 1872", "repealed": True, "successor": "BSA"},
    "BNS": {"name": "Bharatiya Nyaya Sanhita, 2023", "repealed": False, "predecessor": "IPC"},
    "BNSS": {"name": "Bharatiya Nagarik Suraksha Sanhita, 2023", "repealed": False, "predecessor": "CRPC"},
    "BSA": {"name": "Bharatiya Sakshya Adhiniyam, 2023", "repealed": False, "predecessor": "IEA"},
}


def main():
    prov = pd.read_parquet(RAW + "provisions.parquet")
    mp = pd.read_parquet(RAW + "mapping.parquet")
    sections = {}
    for r in prov.itertuples():
        text = " ".join(str(r.text or "").split())
        sections[r.id] = {"h": r.heading or "", "ch": r.chapter_title or "", "t": text[:420],
                          "status": r.status or ""}
    fwd, back = {}, {}
    for r in mp.itertuples():
        rel = {"rel": r.relation, "changed": int(r.changed or 0)}
        if isinstance(r.old_id, str):
            fwd.setdefault(r.old_id, []).append({"to": r.new_id if isinstance(r.new_id, str) else None, **rel})
        if isinstance(r.new_id, str):
            back.setdefault(r.new_id, []).append({"from": r.old_id if isinstance(r.old_id, str) else None, **rel})
    data = {"acts": ACTS, "sections": sections, "old_to_new": fwd, "new_to_old": back,
            "in_force": "2024-07-01",
            "source": "Dhara: Indian criminal law, IPC to BNS (AravArun/dhara-indian-criminal-law, CC-BY-4.0); "
                      "correspondence tables published by NCRB."}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print(len(sections), "sections,", len(fwd), "old->new,", len(back), "new->old;",
          os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
