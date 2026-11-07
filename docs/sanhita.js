/* sanhita.js - browser port of sanhita/cite.py + sanhita/check.py (kept in parity by tests/parity). */
(function (root) {
  "use strict";

  // Make an ASCII-lowercase regex source case-insensitive WITHOUT the i flag, so that
  // section suffixes (498A, 65B) can stay case-sensitive like the Python version.
  function ci(src) {
    let out = "", inClass = false;
    for (let i = 0; i < src.length; i++) {
      const ch = src[i];
      if (ch === "\\") { out += ch + src[i + 1]; i++; continue; }
      if (ch === "[") inClass = true;
      if (ch === "]") inClass = false;
      if (!inClass && /[a-z]/.test(ch)) out += "[" + ch + ch.toUpperCase() + "]";
      else if (inClass && /[a-z]/.test(ch) && src[i + 1] !== "-" && src[i - 1] !== "-") out += ch + ch.toUpperCase();
      else out += ch;
    }
    return out;
  }

  const ACTS = [
    ["BNSS", "bharatiya\\s+nagarik\\s+suraksha\\s+sanhita(?:\\s*,?\\s*2023)?|b\\.?\\s?n\\.?\\s?s\\.?\\s?s\\.?(?![a-z])|भारतीय\\s+नागरिक\\s+सुरक्षा\\s+संहिता|बीएनएसएस"],
    ["BNS", "bharatiya\\s+nyaya\\s+sanhita(?:\\s*,?\\s*2023)?|b\\.\\s?n\\.\\s?s\\.|bns(?![a-z])|भारतीय\\s+न्याय\\s+संहिता|बीएनएस"],
    ["BSA", "bharatiya\\s+sakshya\\s+adhiniyam(?:\\s*,?\\s*2023)?|b\\.\\s?s\\.\\s?a\\.|bsa(?![a-z])|भारतीय\\s+साक्ष्य\\s+अधिनियम\\s*,?\\s*2023"],
    ["IPC", "indian\\s+penal\\s+code(?:\\s*,?\\s*1860)?|penal\\s+code|i\\.\\s?p\\.\\s?c\\.?|ipc(?![a-z])|भारतीय\\s+दंड\\s+संहिता|भा\\.\\s?दं\\.\\s?सं\\.?|आईपीसी"],
    ["CRPC", "code\\s+of\\s+criminal\\s+procedure(?:\\s*,?\\s*1973)?|criminal\\s+procedure\\s+code|cr\\.?\\s?p\\.?\\s?c\\.?(?![a-z])|दंड\\s+प्रक्रिया\\s+संहिता|सीआरपीसी"],
    ["IEA", "(?:indian\\s+)?evidence\\s+act(?:\\s*,?\\s*1872)?|i\\.?\\s?e\\.?\\s?a\\.?(?![a-z])|भारतीय\\s+साक्ष्य\\s+अधिनियम(?:\\s*,?\\s*1872)?"],
  ];
  const ACT_RE = new RegExp(ACTS.map(([a, p]) => `(?<${a}>${ci(p)})`).join("|"), "g");

  const STOPSUF = "(?:OF|TO|OR|IN|AS|IS|ON|AT|BY|AN)\\b";
  const NUM = `\\d{1,3}(?!\\d)(?:(?!\\s?${STOPSUF})\\s?-?\\s?[A-Z]{1,2}(?![A-Za-z])(?!\\.\\s?[A-Za-z]))?(?:\\s?\\(\\s?[0-9a-zA-Z]{1,4}\\s?\\))*(?:\\s+${ci("part")}\\s+(?:I{1,3}|[12])\\b)?`;
  const SEP = "\\s*(?:,|/|&|" + ci("\\band\\b|\\bor\\b|\\bto\\b") + "|-|" + ci("r/w|r\\.w\\.|read\\s+with") + "|के\\s+साथ|एवं|और|तथा|व)\\s*(?:(?:" + ci("sections?|secs?\\.?|ss?\\.") + "|धारा)\\s*)?";
  const LIST = `${NUM}(?:${SEP}${NUM})*`;
  const KW = "(?:" + ci("sections?|secs?\\.?") + "|" + ci("ss?\\.") + "(?=\\s?\\d)|" + ci("s\\.") + "(?=\\s?\\d)|" + ci("u/ss?\\.?|u/s") + "|धाराओं|धारा)";
  const KW_LIST_RE = new RegExp(`(?<![A-Za-z])${KW}\\s*(?<list>${LIST})`, "g");
  const BARE_LIST_RE = new RegExp(`(?<![\\w.])(?<list>${LIST})\\s*(?:,\\s*)?(?:${ci("of")}\\s+(?:${ci("the")}\\s+)?)?$`);
  const NOT_SECTION = new RegExp(ci("(chapter|clause|part|schedule|para(graph)?|exception|explanation|illustration|rule|article|order|item|entry|no\\.?|number|year|of)") + "\\s*$");
  const DIG = { "०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5", "६": "6", "७": "7", "८": "8", "९": "9" };

  function splitList(s) {
    s = s.replace(/[०-९]/g, (d) => DIG[d]);
    const re = new RegExp(NUM, "g");
    const nums = [...s.matchAll(re)];
    const out = [];
    nums.forEach((m, i) => {
      const tok = m[0];
      const sec = tok.replace(/\(.*|\s+[pP][aA][rR][tT]\s+.*/, "").replace(/[\s-]/g, "").toUpperCase();
      const sub = (tok.match(/\(\s?[0-9a-zA-Z]{1,4}\s?\)/g) || []).join("").replace(/ /g, "");
      if (i > 0) {
        const prev = nums[i - 1];
        const between = s.slice(prev.index + prev[0].length, m.index);
        if (/\bto\b|-/i.test(between) && !/,|and|\//i.test(between)) {
          const a = out[out.length - 1][0], b = sec;
          if (/^\d+$/.test(a) && /^\d+$/.test(b) && +b - +a > 0 && +b - +a <= 40)
            for (let k = +a + 1; k < +b; k++) out.push([String(k), ""]);
        }
      }
      out.push([sec, sub]);
    });
    return out;
  }

  function findCitations(text, inferAct = true) {
    const t = text.replace(/[०-९]/g, (d) => DIG[d]);
    const acts = [];
    for (const m of t.matchAll(ACT_RE)) {
      const act = Object.keys(m.groups).find((k) => m.groups[k] !== undefined);
      acts.push([m.index, m.index + m[0].length, act]);
    }
    const cites = [], used = [];
    const actAfter = (pos, limit = 45) => {
      for (const [a0, a1, act] of acts)
        if (a0 >= pos && a0 - pos <= limit && /^[\s,]*(?:of\s+)?(?:the\s+)?(?:under\s+)?(?:की\s+|का\s+|के\s+)?$/i.test(t.slice(pos, a0)))
          return [act, a1];
      return [null, pos];
    };
    const actBefore = (pos, limit = 25) => {
      for (let i = acts.length - 1; i >= 0; i--) {
        const [a0, a1, act] = acts[i];
        if (a1 <= pos && pos - a1 <= limit && /^[\s,]*(?:की\s+|के\s+|का\s+)?(?:sections?|secs?\.?|s\.|धारा)?\s*$/i.test(t.slice(a1, pos)))
          return act;
      }
      return null;
    };
    const add = (start, lst, act, end, inferred = false) => {
      for (const [sec, sub] of splitList(lst))
        cites.push({ act, section: sec, sub, start, end, raw: text.slice(start, end), actInferred: inferred });
      used.push([start, end]);
    };
    for (const m of t.matchAll(KW_LIST_RE)) {
      const lst = m.groups.list;
      const lstEnd = m.index + m[0].length;
      let [act, end] = actAfter(lstEnd);
      if (act === null) { act = actBefore(m.index); end = lstEnd; }
      add(m.index, lst, act, Math.max(end, lstEnd));
    }
    const after = new RegExp(`^\\s*(?:${ci("section")}\\s*|${ci("sec")}\\.?\\s*|${ci("s")}\\.\\s*|की\\s+धारा\\s*)?(?<list>${LIST})`);
    for (const [a0, a1, act] of acts) {
      const m = t.slice(a1).match(after);
      if (m) {
        const ls = a1 + m[0].length - m.groups.list.length;
        if (!used.some(([u0, u1]) => u0 <= ls && ls < u1)) add(a0, m.groups.list, act, a1 + m[0].length);
      }
    }
    for (const [a0, a1, act] of acts) {
      const w0 = Math.max(0, a0 - 60);
      const m = t.slice(w0, a0).match(BARE_LIST_RE);
      if (m) {
        const s0 = w0 + m.index;
        if (NOT_SECTION.test(t.slice(Math.max(0, s0 - 16), s0))) continue;
        if (!used.some(([u0, u1]) => (u0 <= s0 && s0 < u1) || (u0 < a1 && a1 <= u1))) add(s0, m.groups.list, act, a1);
      }
    }
    cites.sort((a, b) => a.start - b.start);
    if (inferAct && acts.length)
      for (const c of cites)
        if (c.act === null) {
          let best = acts[0];
          for (const a of acts) if (Math.abs(a[0] - c.start) < Math.abs(best[0] - c.start)) best = a;
          c.act = best[2]; c.actInferred = true;
        }
    const seen = new Set();
    return cites.filter((c) => { const k = `${c.act}|${c.section}|${c.start}`; if (seen.has(k)) return false; seen.add(k); return true; });
  }

  // ------------------------------------------------------------------ checker
  const OLD = new Set(["IPC", "CRPC", "IEA"]);
  const SUCCESSOR = { IPC: "BNS", CRPC: "BNSS", IEA: "BSA" };
  const PREDECESSOR = { BNS: "IPC", BNSS: "CRPC", BSA: "IEA" };
  const LABEL = { IPC: "IPC", CRPC: "CrPC", IEA: "Evidence Act", BNS: "BNS", BNSS: "BNSS", BSA: "BSA" };
  const STOP = new Set(("a an the of to in on for by with or and any any other is be as at from that this which who whom whose " +
    "shall may under section sections act code person persons whoever such being been has have it its their them his her " +
    "punishment punished imprisonment term years year extend fine also both either description").split(/\s+/));
  const NOTES = {
    "IPC:124A": "Sedition was dropped; BNS 152 (acts endangering sovereignty, unity and integrity of India) is the closest new provision but is not a direct counterpart.",
    "IPC:377": "Dropped; the BNS has no general offence for non-consensual sexual acts between men.",
    "IPC:309": "Attempt to commit suicide is no longer an offence as such; BNS 226 covers attempting suicide to compel or restrain a public servant.",
    "IPC:497": "Adultery was already struck down by the Supreme Court in 2018 (Joseph Shine).",
  };
  let D = null, IDF = null;

  function stem(w) {
    for (const suf of ["ings", "ing", "ers", "er", "ies", "es", "ed", "s"])
      if (w.length > suf.length + 3 && w.endsWith(suf)) return w.slice(0, -suf.length);
    return w;
  }
  const words = (t) => (t.toLowerCase().match(/[a-z]{3,}/g) || []).filter((w) => !STOP.has(w)).map(stem);

  function load(data) {
    D = data;
    const df = new Map();
    const n = Object.keys(D.sections).length;
    for (const s of Object.values(D.sections)) for (const w of new Set(words(s.h + " " + s.t))) df.set(w, (df.get(w) || 0) + 1);
    IDF = new Map([...df].map(([w, c]) => [w, Math.log(n / (1 + c))]));
  }
  const section = (sid) => D.sections[sid];
  const heading = (sid) => (D.sections[sid] ? D.sections[sid].h : null);
  const successors = (sid) => D.old_to_new[sid] || [];
  function fit(sid, ctx) {
    const s = section(sid);
    if (!s) return 0;
    const sw = new Set(words(s.h + " " + s.h + " " + s.t.slice(0, 250)));
    let sc = 0;
    for (const w of new Set(ctx)) if (sw.has(w)) sc += IDF.get(w) || 0;
    return sc;
  }
  const lab = (sid) => `${LABEL[sid.split(":")[0]]} ${sid.split(":")[1]}`;

  function before2024(text) {
    const yrs = (text.match(/\b(19[5-9]\d|20[0-2]\d)\b/g) || []).map(Number);
    if (/before\s+(1(st)?\s+)?july,?\s+2024|prior to (the )?(new|bns)/i.test(text)) return true;
    return yrs.length > 0 && Math.max(...yrs) <= 2023 && !/\b2024\b|\b202[5-9]\b/.test(text);
  }

  function check(text) {
    const cites = findCitations(text);
    const oldPeriod = before2024(text);
    const out = [];
    for (const c of cites) {
      const r = { text: c.raw, start: c.start, end: c.end, act: c.act, section: c.section, sub: c.sub, actInferred: c.actInferred };
      if (c.act === null) { Object.assign(r, { status: "unknown_act", message: `'Section ${c.section}' with no code named.` }); out.push(r); continue; }
      const sid = `${c.act}:${c.section}`;
      const ctx = words(text.slice(Math.max(0, c.start - 220), c.end + 220));
      if (OLD.has(c.act)) {
        if (!section(sid)) Object.assign(r, { status: "nonexistent", message: `${LABEL[c.act]} has no section ${c.section}.` });
        else {
          const succ = successors(sid), tos = succ.filter((s) => s.to).map((s) => s.to);
          r.heading = heading(sid);
          if (!tos.length)
            Object.assign(r, { status: "omitted", message: `${lab(sid)} (${heading(sid)}) was repealed on 1 July 2024 and has no counterpart in the ${LABEL[SUCCESSOR[c.act]]}.` + (NOTES[sid] ? " " + NOTES[sid] : "") });
          else {
            const nw = tos.map((t) => `${lab(t)} (${heading(t)})`).join(", ");
            Object.assign(r, {
              status: oldPeriod ? "ok_old_period" : "stale", suggestion: tos, relation: succ[0].rel,
              message: `${lab(sid)} (${heading(sid)}) was repealed on 1 July 2024. Now: ${nw}.` + (succ[0].rel === "split" ? " The provision was split." : "") +
                (oldPeriod ? " The text dates the events before July 2024, so the old code applies." : " Correct for offences committed before 1 July 2024, which are still tried under the old code."),
            });
          }
        }
      } else {
        const pred = PREDECESSOR[c.act], oldSid = `${pred}:${c.section}`;
        if (!section(sid)) {
          Object.assign(r, { status: "nonexistent", message: `The ${LABEL[c.act]} has no section ${c.section}.` });
          if (section(oldSid)) {
            const tos = successors(oldSid).filter((s) => s.to).map((s) => s.to);
            Object.assign(r, { status: "carryover", suggestion: tos,
              message: `The ${LABEL[c.act]} has no section ${c.section}. This looks like the old ${lab(oldSid)} (${heading(oldSid)})` + (tos.length ? `, which is now ${tos.map(lab).join(", ")}.` : ", which has no successor.") });
          }
        } else {
          r.heading = heading(sid);
          const tos = successors(oldSid).filter((s) => s.to).map((s) => s.to);
          if (section(oldSid) && !tos.includes(sid) && heading(oldSid) !== heading(sid)) {
            const fNew = fit(sid, ctx), fOld = fit(oldSid, ctx);
            if (fOld > 2.0 && fOld > 1.5 * fNew)
              Object.assign(r, { status: "carryover", suggestion: tos,
                message: `${lab(sid)} is '${heading(sid)}', but the text reads like ${lab(oldSid)} ('${heading(oldSid)}'), whose new number is ${tos.map(lab).join(", ") || "none"}.` });
          }
          if (!r.status) {
            if (oldPeriod) Object.assign(r, { status: "temporal", message: `The text dates the events before 1 July 2024; offences from then are tried under the ${LABEL[pred]}, not the ${LABEL[c.act]}.` });
            else Object.assign(r, { status: "ok", message: `${lab(sid)}: ${heading(sid)}.` });
          }
        }
      }
      out.push(r);
    }
    const bad = out.filter((r) => ["stale", "omitted", "nonexistent", "carryover", "temporal"].includes(r.status));
    return { citations: out, issues: bad.length,
      verdict: !bad.length ? "clean" : bad.some((r) => r.status === "nonexistent" || r.status === "carryover") ? "wrong" : "outdated" };
  }

  root.Sanhita = { load, findCitations, check, heading, successors, section, LABEL, lab };
})(typeof window !== "undefined" ? window : globalThis);
