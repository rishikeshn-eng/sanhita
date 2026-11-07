"""Check every statute citation in a piece of text against the law in force.

Statuses
  ok           cites a BNS / BNSS / BSA section that exists and fits the context
  stale        cites an IPC / CrPC / Evidence Act section (repealed 1 July 2024)
               -> the new equivalent, and a reminder that the old code still governs
                  offences committed before that date
  omitted      the old section was dropped with no successor (e.g. IPC 124A sedition)
  nonexistent  the section number does not exist in that code (e.g. "BNS 420")
  carryover    a new-code section that exists, but the text is clearly about the OLD
               section with the same number ("BNS 302" for murder: BNS 302 is about
               religious feelings; murder is BNS 103)
  temporal     new code cited for an offence the text dates before 1 July 2024
  unknown_act  a bare "Section 420" with no code named anywhere
"""
import json
import math
import os
import re
from collections import Counter
from functools import lru_cache

from .cite import find_citations

DATA = os.path.join(os.path.dirname(__file__), "data", "statutes.json")
OLD = {"IPC", "CRPC", "IEA"}
NEW = {"BNS", "BNSS", "BSA"}
SUCCESSOR = {"IPC": "BNS", "CRPC": "BNSS", "IEA": "BSA"}
PREDECESSOR = {v: k for k, v in SUCCESSOR.items()}
LABEL = {"IPC": "IPC", "CRPC": "CrPC", "IEA": "Evidence Act", "BNS": "BNS", "BNSS": "BNSS", "BSA": "BSA"}
STOP = set("""a an the of to in on for by with or and any any other is be as at from that this which who whom whose
shall may under section sections act code person persons whoever such being been has have it its their them his her
punishment punished imprisonment term years year extend fine also both either description""".split())


@lru_cache(maxsize=1)
def statutes():
    d = json.load(open(DATA, encoding="utf-8"))
    df = Counter()
    for s in d["sections"].values():
        df.update(set(_words(s["h"] + " " + s["t"])))
    d["_idf"] = {w: math.log(len(d["sections"]) / (1 + c)) for w, c in df.items()}
    return d


def _stem(w):
    for suf in ("ings", "ing", "ers", "er", "ies", "es", "ed", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _words(t):
    return [_stem(w) for w in re.findall(r"[a-z]{3,}", t.lower()) if w not in STOP]


def section(sid):
    return statutes()["sections"].get(sid)


def heading(sid):
    s = section(sid)
    return s["h"] if s else None


def fit(sid, context_words):
    """IDF-weighted overlap between the context and a section's heading + opening text."""
    s = section(sid)
    if not s:
        return 0.0
    idf = statutes()["_idf"]
    sw = set(_words(s["h"] + " " + s["h"] + " " + s["t"][:250]))
    return sum(idf.get(w, 0) for w in set(context_words) & sw)


def successors(sid):
    return statutes()["old_to_new"].get(sid, [])


NOTES = {
    "IPC:124A": "Sedition was dropped; BNS 152 (acts endangering sovereignty, unity and integrity of India) is the "
                "closest new provision but is not a direct counterpart.",
    "IPC:377": "Dropped; the BNS has no general offence for non-consensual sexual acts between men.",
    "IPC:309": "Attempt to commit suicide is no longer an offence as such; BNS 226 covers attempting suicide to "
               "compel or restrain a public servant.",
    "IPC:497": "Adultery was already struck down by the Supreme Court in 2018 (Joseph Shine).",
}


def _date_before_2024(text):
    yrs = [int(y) for y in re.findall(r"\b(19[5-9]\d|20[0-2]\d)\b", text)]
    if re.search(r"before\s+(1(st)?\s+)?july,?\s+2024|prior to (the )?(new|bns)", text, re.I):
        return True
    return bool(yrs) and max(yrs) <= 2023 and not re.search(r"\b2024\b|\b202[5-9]\b", text)


def check(text):
    cites = find_citations(text)
    out = []
    old_offence_period = _date_before_2024(text)
    for c in cites:
        r = {"text": c.raw, "start": c.start, "end": c.end, "act": c.act, "section": c.section, "sub": c.sub,
             "act_inferred": c.act_inferred}
        if c.act is None:
            r.update(status="unknown_act", message=f"'Section {c.section}' with no code named.")
            out.append(r)
            continue
        sid = f"{c.act}:{c.section}"
        ctx = _words(text[max(0, c.start - 220): c.end + 220])
        if c.act in OLD:
            if not section(sid):
                r.update(status="nonexistent", message=f"{LABEL[c.act]} has no section {c.section}.")
            else:
                succ = successors(sid)
                tos = [s["to"] for s in succ if s.get("to")]
                r["heading"] = heading(sid)
                if not tos:
                    r.update(status="omitted",
                             message=f"{LABEL[c.act]} {c.section} ({heading(sid)}) was repealed on 1 July 2024 and "
                                     f"has no counterpart in the {LABEL[SUCCESSOR[c.act]]}."
                                     + (" " + NOTES[sid] if sid in NOTES else ""))
                else:
                    new = ", ".join(f"{LABEL[t.split(':')[0]]} {t.split(':')[1]} ({heading(t)})" for t in tos)
                    rel = succ[0]["rel"]
                    r.update(status="stale", suggestion=tos, relation=rel,
                             message=f"{LABEL[c.act]} {c.section} ({heading(sid)}) was repealed on 1 July 2024. "
                                     f"Now: {new}." + (" The provision was split." if rel == "split" else "")
                                     + (" Correct for offences committed before 1 July 2024, which are still tried "
                                        "under the old code." if not old_offence_period else
                                        " The text dates the events before July 2024, so the old code applies."))
                    if old_offence_period:
                        r["status"] = "ok_old_period"
        else:  # new code
            pred = PREDECESSOR[c.act]
            old_sid = f"{pred}:{c.section}"
            if not section(sid):
                r.update(status="nonexistent", message=f"The {LABEL[c.act]} has no section {c.section}.")
                if section(old_sid):
                    tos = [s["to"] for s in successors(old_sid) if s.get("to")]
                    r.update(status="carryover", suggestion=tos,
                             message=f"The {LABEL[c.act]} has no section {c.section}. This looks like the old "
                                     f"{LABEL[pred]} {c.section} ({heading(old_sid)})"
                                     + (f", which is now {', '.join(LABEL[t.split(':')[0]] + ' ' + t.split(':')[1] for t in tos)}." if tos else
                                        ", which has no successor."))
            else:
                r["heading"] = heading(sid)
                tos = [s["to"] for s in successors(old_sid) if s.get("to")]
                same = sid in tos
                if section(old_sid) and not same and heading(old_sid) != heading(sid):
                    f_new, f_old = fit(sid, ctx), fit(old_sid, ctx)
                    if f_old > 2.0 and f_old > 1.5 * f_new:
                        r.update(status="carryover", suggestion=tos, fit={"cited": round(f_new, 2), "old": round(f_old, 2)},
                                 message=f"{LABEL[c.act]} {c.section} is '{heading(sid)}', but the text reads like "
                                         f"{LABEL[pred]} {c.section} ('{heading(old_sid)}'), whose new number is "
                                         f"{', '.join(LABEL[t.split(':')[0]] + ' ' + t.split(':')[1] for t in tos) or 'none'}.")
                if "status" not in r:
                    if old_offence_period:
                        r.update(status="temporal", message=f"The text dates the events before 1 July 2024; offences "
                                                            f"from then are tried under the {LABEL[pred]}, not the {LABEL[c.act]}.")
                    else:
                        r.update(status="ok", message=f"{LABEL[c.act]} {c.section}: {heading(sid)}.")
        out.append(r)
    bad = [r for r in out if r["status"] in ("stale", "omitted", "nonexistent", "carryover", "temporal")]
    return {"citations": out, "issues": len(bad),
            "verdict": "clean" if not bad else ("wrong" if any(r["status"] in ("nonexistent", "carryover") for r in bad)
                                                else "outdated")}
