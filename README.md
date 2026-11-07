# sanhita

**Your legal AI is still citing a law India repealed.**

[**Live checker →**](https://rishikeshn-eng.github.io/sanhita/) Paste any chatbot answer, FIR draft or news report. Every statute citation is checked against the law in force, entirely in your browser.

---

On **1 July 2024** India replaced the Indian Penal Code, the Code of Criminal Procedure and the Evidence Act with the
**Bharatiya Nyaya Sanhita (BNS)**, the **Bharatiya Nagarik Suraksha Sanhita (BNSS)** and the **Bharatiya Sakshya Adhiniyam (BSA)**.
Almost every section was renumbered. Language models learned the old numbers, and the old numbers *still exist* in the new codes with
different meanings:

| What a model says | What it actually cites | What it should say |
|---|---|---|
| “Murder is punishable under **BNS 302**” | BNS 302 = *uttering words to wound religious feelings* | **BNS 103** |
| “Cheating is covered by **Section 420 of the BNS**” | the BNS stops at section 358 | **BNS 318** |
| “File an FIR under **Section 154 CrPC**” | repealed | **BNSS 173** |
| “Sedition under **Section 124A IPC**” | omitted, no direct counterpart | (closest: BNS 152) |

Lookup tables for the new codes already exist (e.g. NCRB's Sankalan app). What nobody does is **check what AI systems actually say**.
sanhita does that, measures how often models get it wrong, tests whether fine-tuning fixes it, and audits the data Indian legal
chatbots are trained on.

```python
>>> from sanhita import check
>>> check("Murder is punishable under BNS 302.")["citations"][0]["status"]
'carryover'          # BNS 302 is about religious feelings; murder is BNS 103
```

## What it checks

| status | meaning |
|---|---|
| `stale` | cites IPC / CrPC / Evidence Act → gives the new section(s), and notes the old code still governs offences committed **before** 1 July 2024 |
| `omitted` | the old section has no successor (124A sedition, 377, 309) |
| `nonexistent` | the section number doesn't exist in that code |
| `carryover` | a new-code section that exists, but the surrounding text matches the *old* section with that number far better |
| `temporal` | a new-code citation for events the text dates before July 2024 |
| `ok` / `ok_old_period` | correct |

Carry-over detection compares IDF-weighted word overlap between the text around the citation and the headings/opening text of both
candidate sections. Dates in the text decide which code applies.

## Results

### Benchmark: 740 questions, gold answers from NCRB's official correspondence tables

| Model | old→new correct | …gave the old number | names the section in force | …cited repealed / carried-over | real-life scenarios | 2022 offence → IPC | 2025 offence → BNS |
|---|---|---|---|---|---|---|---|
| Gemma 3 1B | 0% | 74% | 0% | 51% | 0% | 0% | 0% |
| Llama 3.2 3B | 0% | 0% | 0% | 0% | 0% | 23% | 0% |
| Phi-4 mini 3.8B | 0% | 42% | 0% | 2% | 0% | 20% | 0% |
| Qwen3 1.7B + our LoRA | 10% | 0% | 0% | 37% | 0% | 0% | 0% |
| Qwen3 1.7B | 1% | 59% | 0% | 46% | 0% | 3% | 0% |
| Qwen3 8B | 0% | 37% | 0% | 70% | 0% | 33% | 0% |

“Gave the old number” on conversion questions is the carry-over error; 34% of answers on average cite a repealed section
or an old number on the new code. Local models ran 4-bit on an Apple M4 (MLX, greedy decoding). Llama 3.2 · 3B refused 86% of plain-language questions about the law (e.g. a woman asking which law covers an acid attack) as “illegal or harmful activities”.

### Can fine-tuning fix it? (LoRA on Qwen3 1.7B, 80/20 split by section)

| | before | after LoRA |
|---|---|---|
| old → new, sections it was trained on | 1% | **10%** |
| old → new, sections it never saw | 0% | 8% |
| “which section covers…”, trained sections | 0% | 0% |
| “which section covers…”, unseen sections | 0% | 0% |
| 2022 offence still placed under the IPC | 3% | 0% |
| ARC-Easy (general knowledge) | 86% | 64% |

600 LoRA steps on 5,805 examples moved old→new conversion from 1% to 10% on trained sections and to 8% on sections it never saw: about the same, so it learned the answer format, not the law. Meanwhile general knowledge (ARC-Easy) fell from 86% to 64% and it stopped placing 2022 offences under the IPC. Retraining a small model is the wrong tool; checking answers against the official table (what sanhita does) is the fix.

### The data legal chatbots are trained on

| Hugging Face dataset | downloads | examples | cite a criminal code | cite only repealed codes, no mention of the 2023 laws |
|---|---|---|---|---|
| `jizzu/llama2_indian_law_v2` | 37 | 25,338 | 114 | **114** (100%) |
| `viber1/indian-law-dataset` | 91 | 24,607 | 65 | **65** (100%) |
| `shruths204/basic-legal-qa-india` | 4 | 1,500 | 0 | **0** (–) |
| `nisaar/Lawyer_GPT_India` | 87 | 200 | 7 | **7** (100%) |
| `Mukesh555/indian_lawyer_dataset` | 6 | 1,000 | 6 | **6** (100%) |
| `Akshatpunia0912/Indian-Laws (+3 identical copies)` | 7,502 | 34,244 | 724 | **722** (100%) |
| `GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA (new-law control)` | 258 | 6,354 | 6,354 | **0** (0%) |

Even the Supreme Court is mid-transition: in 2025 its judgments cite the old codes 9,129 times and the new ones
457 times. Most of those old citations are correct, because offences committed before 1 July 2024 are still tried under the
IPC, which is why sanhita reports *when* each code applies instead of flagging every IPC citation as an error.

### The citation parser

Precision **99.5%**, recall **99.1%** on 102,045 real
citation strings from Supreme Court judgments (`bench/eval_extractor.py`).

## Install & use

```bash
pip install -e .                      # no runtime dependencies
sanhita "Murder is punishable under BNS 302."
sanhita --map IPC 420                 # IPC 420 → BNS 318 Cheating (merged)
echo "$CHATBOT_REPLY" | sanhita -     # exit 0 clean · 1 outdated · 2 wrong
sanhita --json "..."
```

Use it as an output filter on any legal-information chatbot: block or annotate answers whose verdict is `wrong`, append the
new-code equivalents to answers that are `outdated`.

## Reproduce

```
pipeline/build_data.py       statutes + official mapping from Dhara (CC-BY-4.0) → sanhita/data/statutes.json
bench/eval_extractor.py      citation parser vs 102,045 Supreme Court citation strings
bench/make_tasks.py          the 740-question benchmark (gold answers from the official tables)
bench/llm.py                 runs local models (MLX) and Gemini; resumable
bench/score.py               correct / stale / carry-over / wrong / none
bench/audit.py               training-data audit + Supreme Court citation trend
lora/run.sh                  LoRA knowledge-update experiment on Qwen3-1.7B
tests/                       27 unit tests + Python↔JavaScript parity test (tests/parity)
```

The browser checker (`docs/sanhita.js`) is a line-by-line port of the Python, and produces identical output on 3,085 test strings
(3,077 real Supreme Court citations + edge cases).

## Limitations

- sanhita checks **citations**, not legal reasoning. It cannot tell whether a correctly numbered section actually fits the facts.
- The mapping is NCRB's official correspondence table. Where a provision was split or merged, sanhita lists every counterpart rather
  than choosing one.
- Carry-over detection is lexical. A very short answer ("BNS 302 applies") gives it little context, and it will stay quiet rather than guess.
- Date handling is a heuristic over years mentioned in the text; it does not model procedural transition rules in detail.
- Gemini could not be evaluated here: the free API tier's daily quota was exhausted by the companion medicine benchmark.

Not legal advice.

## Data & credits

Statute text and the old↔new correspondence: [Dhara](https://huggingface.co/datasets/AravArun/dhara-indian-criminal-law)
(CC-BY-4.0), built from NCRB's published tables, including 159,686 citations from 9,686 Supreme Court judgments. Training-data
audit covers public Hugging Face datasets listed in `bench/out/audit.json`. MIT licensed.
