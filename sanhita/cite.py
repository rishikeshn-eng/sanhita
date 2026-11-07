"""Find statute citations in English or Hindi text.

Handles the ways Indian lawyers, judges, journalists and chatbots actually write them:
  "Section 302 IPC", "u/s 498-A of the Indian Penal Code", "302/34 IPC",
  "Sections 447, 506 read with Section 34 of the IPC", "Sections 63 to 70, IPC",
  "S. 161(2) Cr.P.C.", "BNS 103(1)", "Section 65B of the Evidence Act",
  "धारा 420 भारतीय दंड संहिता", "बीएनएस की धारा 318".
"""
import re
from dataclasses import dataclass

_ACT_PATTERNS = [
    ("BNSS", r"bharatiya\s+nagarik\s+suraksha\s+sanhita(?:\s*,?\s*2023)?|b\.?\s?n\.?\s?s\.?\s?s\.?(?![a-z])|"
             r"भारतीय\s+नागरिक\s+सुरक्षा\s+संहिता|बीएनएसएस"),
    ("BNS", r"bharatiya\s+nyaya\s+sanhita(?:\s*,?\s*2023)?|b\.\s?n\.\s?s\.|bns(?![a-z])|"
            r"भारतीय\s+न्याय\s+संहिता|बीएनएस"),
    ("BSA", r"bharatiya\s+sakshya\s+adhiniyam(?:\s*,?\s*2023)?|b\.\s?s\.\s?a\.|bsa(?![a-z])|"
            r"भारतीय\s+साक्ष्य\s+अधिनियम\s*,?\s*2023"),
    ("IPC", r"indian\s+penal\s+code(?:\s*,?\s*1860)?|penal\s+code|i\.\s?p\.\s?c\.?|ipc(?![a-z])|"
            r"भारतीय\s+दंड\s+संहिता|भा\.\s?दं\.\s?सं\.?|आईपीसी"),
    ("CRPC", r"code\s+of\s+criminal\s+procedure(?:\s*,?\s*1973)?|criminal\s+procedure\s+code|"
             r"cr\.?\s?p\.?\s?c\.?(?![a-z])|दंड\s+प्रक्रिया\s+संहिता|सीआरपीसी"),
    ("IEA", r"(?:indian\s+)?evidence\s+act(?:\s*,?\s*1872)?|i\.?\s?e\.?\s?a\.?(?![a-z])|"
            r"भारतीय\s+साक्ष्य\s+अधिनियम(?:\s*,?\s*1872)?"),
]
ACT_RE = re.compile("|".join(f"(?P<{a}>{p})" for a, p in _ACT_PATTERNS), re.I)

_DIG = str.maketrans("०१२३४५६७८९", "0123456789")
# letter suffixes (498A, 65B, 304-B) are matched case-SENSITIVELY so "63 to 70" isn't read as "63TO"
# ...and never when they are the start of an abbreviation ("420 I.P.C." is not section 420I)
NUM = (r"\d{1,3}(?!\d)(?:(?!\s?(?-i:OF|TO|OR|IN|AS|IS|ON|AT|BY|AN)\b)(?-i:\s?-?\s?[A-Z]{1,2})(?![A-Za-z])"
       r"(?!\.\s?[A-Za-z]))?(?:\s?\(\s?[0-9a-zA-Z]{1,4}\s?\))*"
       r"(?:\s+part\s+(?:I{1,3}|[12])\b)?")
SEP = r"\s*(?:,|/|&|\band\b|\bor\b|\bto\b|-|r/w|r\.w\.|read\s+with|के\s+साथ|एवं|और|तथा|व)\s*(?:(?:sections?|secs?\.?|ss?\.|धारा)\s*)?"
LIST = rf"{NUM}(?:{SEP}{NUM})*"
KW = r"(?:sections?|secs?\.?|ss?\.(?=\s?\d)|s\.(?=\s?\d)|u/ss?\.?|u/s|धाराओं|धारा|अनुच्छेद(?!))"
KW_LIST_RE = re.compile(rf"(?<![A-Za-z]){KW}\s*(?P<list>{LIST})", re.I)
BARE_LIST_RE = re.compile(rf"(?<![\w.])(?P<list>{LIST})\s*(?:,\s*)?(?:of\s+(?:the\s+)?)?$", re.I)
NOT_SECTION = re.compile(r"(chapter|clause|part|schedule|para(graph)?|exception|explanation|illustration|"
                         r"rule|article|order|item|entry|no\.?|number|year|of)\s*$", re.I)


@dataclass
class Citation:
    act: str | None      # IPC, CRPC, IEA, BNS, BNSS, BSA or None if not stated
    section: str         # "302", "498A", "65B"
    sub: str             # "(2)" etc.
    start: int
    end: int
    raw: str
    act_inferred: bool = False

    @property
    def id(self):
        return f"{self.act}:{self.section}" if self.act else None


def _split_list(s):
    """'447, 506 read with Section 34' -> ['447','506','34']; '63 to 70' -> range."""
    s = s.translate(_DIG)
    nums = list(re.finditer(NUM, s))
    out = []
    for i, m in enumerate(nums):
        tok = m.group(0)
        sec = re.sub(r"[\s\-]", "", re.sub(r"\(.*|\s+part\s+.*", "", tok, flags=re.I)).upper()
        sub = "".join(re.findall(r"\(\s?[0-9a-zA-Z]{1,4}\s?\)", tok)).replace(" ", "")
        if i > 0:
            between = s[nums[i - 1].end():m.start()]
            if re.search(r"\bto\b|-", between) and not re.search(r",|and|/", between):
                a, b = out[-1][0], sec
                if a.isdigit() and b.isdigit() and 0 < int(b) - int(a) <= 40:
                    out.extend((str(k), "") for k in range(int(a) + 1, int(b)))
        out.append((sec, sub))
    return out


def find_citations(text, infer_act=True):
    t = text.translate(_DIG)
    acts = [(m.start(), m.end(), next(k for k, v in m.groupdict().items() if v)) for m in ACT_RE.finditer(t)]
    cites, used = [], []

    def act_after(pos, limit=45):
        for a0, a1, act in acts:
            if a0 >= pos and a0 - pos <= limit and re.fullmatch(r"[\s,]*(?:of\s+)?(?:the\s+)?(?:under\s+)?(?:की\s+|का\s+|के\s+)?",
                                                                    t[pos:a0], re.I):
                return act, a1
        return None, pos

    def act_before(pos, limit=25):
        for a0, a1, act in reversed(acts):
            if a1 <= pos and pos - a1 <= limit and re.fullmatch(r"[\s,]*(?:की\s+|के\s+|का\s+)?(?:sections?|secs?\.?|s\.|धारा)?\s*",
                                                                    t[a1:pos], re.I):
                return act
        return None

    def add(lst_start, lst_end, lst, act, end, inferred=False):
        for sec, sub in _split_list(lst):
            cites.append(Citation(act, sec, sub, lst_start, end, text[lst_start:end], inferred))
        used.append((lst_start, end))

    # 1. keyword-led lists: "Section 302 of the IPC", "u/s 498-A IPC", "IPC Section 302", "धारा 302"
    for m in KW_LIST_RE.finditer(t):
        lst = m.group("list")
        act, end = act_after(m.end("list"))
        if act is None:
            act = act_before(m.start())
            end = m.end("list")
        add(m.start(), m.end("list"), lst, act, max(end, m.end("list")))
    # 2. act followed directly by numbers: "BNS 103(1)", "IPC 420", "BNSS 173"
    for a0, a1, act in acts:
        m = re.match(rf"\s*(?:section\s*|sec\.?\s*|s\.\s*|की\s+धारा\s*)?(?P<list>{LIST})", t[a1:], re.I)
        if m and not any(u0 <= a1 + m.start("list") < u1 for u0, u1 in used):
            add(a0, a1 + m.end("list"), m.group("list"), act, a1 + m.end("list"))
    # 3. bare numbers right before an act: "302/34 IPC", "302 IPC"
    for a0, a1, act in acts:
        m = BARE_LIST_RE.search(t[max(0, a0 - 60):a0])
        if m:
            s0 = max(0, a0 - 60) + m.start("list")
            if NOT_SECTION.search(t[max(0, s0 - 16):s0]):
                continue  # "Chapter 16 of the IPC", "Exception 4 to ..." are not section citations
            if not any(u0 <= s0 < u1 or u0 < a1 <= u1 for u0, u1 in used):
                add(s0, a1, m.group("list"), act, a1)
    cites.sort(key=lambda c: c.start)
    # 4. act-less citations inherit the nearest act named in the same text (marked as inferred)
    if infer_act:
        named = [c for c in cites if c.act]
        for c in cites:
            if c.act is None and acts:
                near = min(acts, key=lambda a: abs(a[0] - c.start))
                c.act, c.act_inferred = near[2], True
    # de-duplicate
    seen, out = set(), []
    for c in cites:
        k = (c.act, c.section, c.start)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out
