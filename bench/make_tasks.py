"""Build the sanhita LLM benchmark -> bench/prompts.jsonl, bench/tasks_meta.json

S1  convert    "Which BNS section corresponds to IPC 420 (Cheating...)?"      300 items
S2  current    "Under the law in force today, which section covers <offence>?" 300 items
S3  scenario   plain-language situations ("my phone was stolen on a bus...")    80 items
S4  temporal   the same offence dated 2022 vs 2025: which code applies?         60 items
Gold answers come from NCRB's official correspondence tables (via Dhara).
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sanhita.check import statutes, heading, successors, LABEL  # noqa: E402

HERE = os.path.dirname(__file__)
rng = random.Random(2024)
d = statutes()
FULL = {k: v["name"] for k, v in d["acts"].items()}
prompts, meta = [], {}


def add(pid, task, prompt, max_tokens, **m):
    prompts.append({"id": pid, "prompt": prompt, "max_tokens": max_tokens})
    meta[pid] = {"task": task, **m}


def mapped(act, rels=("equivalent", "merged", "split", "partial")):
    out = []
    for sid, succ in d["old_to_new"].items():
        if not sid.startswith(act + ":"):
            continue
        tos = [s["to"] for s in succ if s.get("to")]
        if tos and succ[0]["rel"] in rels and heading(sid) and sid.split(":")[1] not in ("1", "2", "3", "4"):
            out.append((sid, tos))
    return sorted(out)


pool = {a: mapped(a) for a in ("IPC", "CRPC", "IEA")}
# a number is a "carry-over trap" when the same number exists in the new code with a different meaning
for a, n in (("IPC", 180), ("CRPC", 80), ("IEA", 40)):
    for sid, tos in rng.sample(pool[a], n):
        num = sid.split(":")[1]
        new = tos[0].split(":")[0]
        add(f"conv-{sid}", "convert",
            f"India replaced the {FULL[a]} with the {FULL[new]} on 1 July 2024. Which section of the {FULL[new]} "
            f"corresponds to Section {num} of the {FULL[a]} ('{heading(sid)}')? Reply with only the section number.",
            24, old=sid, gold=tos, new_act=new)
for a, n in (("IPC", 200), ("CRPC", 70), ("IEA", 30)):
    for sid, tos in rng.sample(pool[a], n):
        add(f"cur-{sid}", "current",
            f"Under the criminal law in force in India today (since 1 July 2024), which section of which Act deals with: "
            f"'{heading(sid)}'? Reply in the form 'Act, Section number', e.g. 'XYZ Act, Section 12'.",
            40, old=sid, gold=tos, new_act=tos[0].split(":")[0])

SCEN = [  # (old section, situation)
    ("IPC:379", "Someone stole my phone from my bag on a crowded bus last week."),
    ("IPC:420", "A man took Rs 50,000 from me promising a government job and then disappeared."),
    ("IPC:498A", "My husband and in-laws keep harassing me and beating me for more dowry."),
    ("IPC:302", "My neighbour's son was killed in a fight last night; the police have arrested the attacker."),
    ("IPC:307", "A man stabbed my brother intending to kill him, but he survived."),
    ("IPC:323", "My neighbour slapped and punched me during an argument over parking."),
    ("IPC:325", "During a fight someone broke my father's arm with a rod."),
    ("IPC:354D", "A man keeps following my sister to college and messaging her even after she refused him."),
    ("IPC:354A", "My manager keeps making sexual remarks and demands favours at work."),
    ("IPC:509", "A man on the street made obscene gestures and comments to insult a woman."),
    ("IPC:506", "My landlord threatened to kill me if I don't vacate the flat."),
    ("IPC:500", "A person posted false statements to ruin my reputation in my community."),
    ("IPC:406", "My business partner kept money I trusted him with and refuses to return it."),
    ("IPC:304B", "A woman died under suspicious circumstances two years after marriage after dowry demands."),
    ("IPC:306", "My cousin took his own life after his employer constantly humiliated and threatened him."),
    ("IPC:279", "A car was being driven dangerously fast on a busy road and endangered people."),
    ("IPC:304A", "A truck driver's negligence caused the death of a cyclist."),
    ("IPC:363", "A child was taken away from his parents without their consent."),
    ("IPC:384", "A local goon is forcing shopkeepers to pay him money every month by threatening them."),
    ("IPC:392", "Two men on a bike snatched my gold chain at knifepoint."),
    ("IPC:411", "Someone is knowingly selling phones that were stolen."),
    ("IPC:465", "A person forged my signature on a property document."),
    ("IPC:427", "My neighbour deliberately damaged my car's windshield."),
    ("IPC:448", "A man entered my house without permission to intimidate my family."),
    ("IPC:354", "A man groped a woman in a crowded market."),
    ("IPC:376", "A woman has been sexually assaulted and wants to file a police complaint."),
    ("IPC:326A", "A man threw acid on a woman's face."),
    ("IPC:147", "A group of people started rioting and damaging shops in our area."),
    ("CRPC:154", "I want the police to register an FIR for a cognizable offence."),
    ("CRPC:438", "I fear I may be arrested in a false case and want protection from arrest in advance."),
    ("CRPC:125", "My husband has left me and our children without any financial support."),
    ("CRPC:41", "When can the police arrest someone without a warrant?"),
    ("IEA:65B", "I want to use WhatsApp chats and CCTV footage as evidence in court."),
    ("IEA:32", "The victim told the doctor who attacked her just before she died."),
    ("IEA:25", "The police say the accused confessed to them in custody."),
    ("CRPC:164", "The magistrate wants to record the statement of a witness."),
    ("CRPC:167", "The police want to keep the accused in custody beyond 24 hours."),
    ("CRPC:482", "The accused wants the High Court to quash a false FIR."),
    ("IPC:120B", "Three people planned together to rob a bank."),
    ("IPC:34", "Two people together beat up a man; both shared the same intention."),
]
for sid, situation in SCEN:
    tos = [s["to"] for s in successors(sid) if s.get("to")]
    if not tos:
        continue
    for k, phr in enumerate((
            "{s} This happened in 2025 in India. Which section(s) of law apply? Answer briefly and cite the sections.",
            "{s} Yeh 2025 mein India mein hua. Kaunsi section lagegi? Short mein batao aur section number do.")):
        add(f"scn-{sid}-{k}", "scenario", phr.format(s=situation), 160, old=sid, gold=tos, new_act=tos[0].split(":")[0])

TEMP = rng.sample([s for s in SCEN if s[0].startswith("IPC")], 30)
for sid, situation in TEMP:
    tos = [s["to"] for s in successors(sid) if s.get("to")]
    for yr in (2022, 2025):
        add(f"tmp-{sid}-{yr}", "temporal",
            f"{situation.split('.')[0]}. This happened in {yr} and the trial starts now. Under which Act and section "
            f"will the accused be charged? Answer in one line.", 60,
            old=sid, gold=tos if yr == 2025 else [sid], year=yr, new_act=tos[0].split(":")[0])

with open(os.path.join(HERE, "prompts.jsonl"), "w", encoding="utf-8") as f:
    for p in prompts:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
json.dump(meta, open(os.path.join(HERE, "tasks_meta.json"), "w"), ensure_ascii=False, indent=0)
from collections import Counter
print(Counter(m["task"] for m in meta.values()))
traps = sum(1 for m in meta.values() if m["task"] == "convert" and
            f"{m['new_act']}:{m['old'].split(':')[1]}" in d["sections"] and
            f"{m['new_act']}:{m['old'].split(':')[1]}" not in m["gold"])
print("convert items where the old number also exists (with another meaning) in the new code:", traps)
