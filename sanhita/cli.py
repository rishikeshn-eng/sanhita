"""sanhita command line.

  sanhita "Murder is punishable under BNS 302."      # check a legal answer
  sanhita --map IPC 420                             # what replaced a section
  echo "$CHATBOT_REPLY" | sanhita -                 # check before showing it
  sanhita --json "..."

Exit code: 0 clean, 1 outdated citations, 2 wrong citations (non-existent / carry-over).
"""
import argparse
import json
import sys

RED, YEL, GRN, DIM, B, R = "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[1m", "\033[0m"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sanhita", description="Check Indian criminal-law citations against the 2023 codes.")
    ap.add_argument("text", nargs="*")
    ap.add_argument("--map", nargs=2, metavar=("ACT", "SECTION"), help="e.g. --map IPC 420")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    color = sys.stdout.isatty() and not a.json
    c = (lambda code, s: f"{code}{s}{R}") if color else (lambda code, s: s)
    from .check import check, heading, successors, statutes, LABEL

    if a.map:
        act = a.map[0].upper().replace(".", "")
        act = {"CRPC": "CRPC", "EVIDENCE": "IEA"}.get(act, act)
        sid = f"{act}:{a.map[1].upper()}"
        if a.json:
            print(json.dumps({"section": sid, "heading": heading(sid), "successors": successors(sid),
                              "predecessors": statutes()["new_to_old"].get(sid, [])}, indent=1))
            return 0
        if not heading(sid):
            print(f"{LABEL.get(act, act)} has no section {a.map[1]}.")
            return 1
        print(c(B, f"{LABEL[act]} {a.map[1]}") + f"  {heading(sid)}")
        for s in successors(sid):
            t = s.get("to")
            print(f"  → {c(GRN, LABEL[t.split(':')[0]] + ' ' + t.split(':')[1]) + '  ' + heading(t) if t else c(RED, 'omitted, no successor')}"
                  f"  {c(DIM, s['rel'])}")
        for s in statutes()["new_to_old"].get(sid, []):
            f = s.get("from")
            print(f"  ← {LABEL[f.split(':')[0]] + ' ' + f.split(':')[1] + '  ' + heading(f) if f else 'new provision'}")
        return 0

    text = sys.stdin.read() if (not a.text or a.text == ["-"]) else " ".join(a.text)
    r = check(text)
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
    else:
        col = {"ok": GRN, "ok_old_period": GRN, "stale": YEL, "temporal": YEL, "omitted": YEL, "unknown_act": DIM,
               "nonexistent": RED, "carryover": RED}
        for x in r["citations"]:
            print(f"  {c(col[x['status']], x['status'].upper()):>14}  {c(B, x['text'].strip())}\n{'':16}{x['message']}")
        if not r["citations"]:
            print(c(DIM, "  no statute citations found"))
        v = {"clean": c(GRN, "CLEAN"), "outdated": c(YEL, "OUTDATED"), "wrong": c(RED, "WRONG")}[r["verdict"]]
        print(f"\nVerdict: {v}")
    return {"clean": 0, "outdated": 1, "wrong": 2}[r["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
