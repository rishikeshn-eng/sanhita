"""Fill the <!-- RESULTS --> block of README.md from bench/out/*.json."""
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
R = json.load(open(os.path.join(ROOT, "docs", "data", "report.json")))
pct = lambda x: "–" if x is None else f"{x * 100:.0f}%"


def main():
    rows = []
    for m in R["models"]:
        t = m["tasks"]
        g = lambda k, f="correct": (t[k].get(f, 0) if k in t else None)
        rows.append(f"| {m['label'].replace(' · ', ' ')} | {pct(g('convert'))} | {pct(g('convert', 'carryover'))} | "
                    f"{pct(g('current'))} | {pct((g('current', 'stale') or 0) + (g('current', 'carryover') or 0))} | "
                    f"{pct(g('scenario'))} | {pct(g('temporal_2022'))} | {pct(g('temporal_2025'))} |")
    L = R.get("lora")
    lora = ""
    if L:
        b, a = L["base"], L["lora"]
        c = lambda d, k: pct((d.get(k) or {}).get("correct"))
        lora = f"""
### Can fine-tuning fix it? (LoRA on Qwen3 1.7B, 80/20 split by section)

| | before | after LoRA |
|---|---|---|
| old → new, sections it was trained on | {c(b, 'convert:trained')} | **{c(a, 'convert:trained')}** |
| old → new, sections it never saw | {c(b, 'convert:heldout')} | {c(a, 'convert:heldout')} |
| “which section covers…”, trained sections | {c(b, 'current:trained')} | {c(a, 'current:trained')} |
| “which section covers…”, unseen sections | {c(b, 'current:heldout')} | {c(a, 'current:heldout')} |
| 2022 offence still placed under the IPC | {c(b, 'temporal:2022')} | {c(a, 'temporal:2022')} |
| ARC-Easy (general knowledge) | {pct(L.get('arc_base'))} | {pct(L.get('arc_lora'))} |

{L.get('takeaway', '')}
"""
    A = R["audit"]
    arows = "\n".join(f"| `{k}` | {d['downloads'] or 0:,} | {d['examples']:,} | {d['cite_criminal_code']:,} | "
                      f"**{d['teach_repealed_as_current']:,}** ({pct(d['share_of_citing_examples_stale'])}) |"
                      for k, d in A["datasets"].items())
    sc = A["supreme_court_by_year"]
    res = f"""### Benchmark: 740 questions, gold answers from NCRB's official correspondence tables

| Model | old→new correct | …gave the old number | names the section in force | …cited repealed / carried-over | real-life scenarios | 2022 offence → IPC | 2025 offence → BNS |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

“Gave the old number” on conversion questions is the carry-over error; {R['hero'][1]['v']} of answers on average cite a repealed section
or an old number on the new code. Local models ran 4-bit on an Apple M4 (MLX, greedy decoding). {R['bench_note'].split('Note the refusals: ')[-1]}
{lora}
### The data legal chatbots are trained on

| Hugging Face dataset | downloads | examples | cite a criminal code | cite only repealed codes, no mention of the 2023 laws |
|---|---|---|---|---|
{arows}

Even the Supreme Court is mid-transition: in 2025 its judgments cite the old codes {sc['2025']['old']:,} times and the new ones
{sc['2025']['new']:,} times. Most of those old citations are correct, because offences committed before 1 July 2024 are still tried under the
IPC, which is why sanhita reports *when* each code applies instead of flagging every IPC citation as an error.

### The citation parser

Precision **{R['extractor']['precision'] * 100:.1f}%**, recall **{R['extractor']['recall'] * 100:.1f}%** on {R['extractor']['strings']:,} real
citation strings from Supreme Court judgments (`bench/eval_extractor.py`)."""
    p = os.path.join(ROOT, "README.md")
    s = open(p).read()
    if "<!-- RESULTS -->" in s:
        s = s.replace("<!-- RESULTS -->", res)
        open(p, "w").write(s)
        print("README filled")


if __name__ == "__main__":
    main()
