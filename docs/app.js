/* sanhita site: live checker, lookup, and results rendered from data/report.json */
(async function () {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  $("#today").textContent = new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });

  const [statutes, R] = await Promise.all([fetch("data/statutes.json").then((r) => r.json()),
    fetch("data/report.json").then((r) => r.json()).catch(() => null)]);
  Sanhita.load(statutes);

  // ---------------------------------------------------------------- checker
  const EX = [
    ["Chatbot: murder", "Q: What is the punishment for murder in India?\nA: Murder is punishable under Section 302 of the Bharatiya Nyaya Sanhita (BNS) with death or imprisonment for life, and fine. Culpable homicide not amounting to murder is covered under Section 304."],
    ["FIR advice", "Someone cheated me online. You should file an FIR under Section 154 CrPC for cheating under Section 420 IPC, and if documents were forged add Sections 467, 468 and 471 IPC. WhatsApp screenshots need a certificate u/s 65B of the Evidence Act."],
    ["Correct (new codes)", "Cheating is punishable under BNS 318(4). The police must register an FIR under BNSS 173, and electronic records are admissible under BSA 63."],
    ["Hindi", "धोखाधड़ी के मामले में धारा 420 भारतीय दंड संहिता के तहत शिकायत दर्ज करें। दहेज उत्पीड़न के लिए धारा 498A लगेगी।"],
    ["Old case (2023)", "The accused stole a motorcycle in March 2023, so he is being tried under Section 379 IPC; the prosecution also invoked BNS 303."],
    ["Sedition", "He was arrested for sedition under Section 124A IPC."],
  ];
  const exBox = $("#examples");
  EX.forEach(([label, text], i) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.onclick = () => { $("#input").value = text; run(); };
    exBox.appendChild(b);
  });
  const STAMP = { ok: "in force", ok_old_period: "old code ok", stale: "repealed", omitted: "omitted", temporal: "wrong period",
    carryover: "carry-over", nonexistent: "no such section", unknown_act: "which act?" };
  function run() {
    const text = $("#input").value;
    const r = Sanhita.check(text);
    let html = "", pos = 0;
    const spans = [...r.citations].sort((a, b) => a.start - b.start);
    const merged = [];
    for (const c of spans) {
      const last = merged[merged.length - 1];
      if (last && c.start < last.end) { if (rank(c.status) > rank(last.status)) last.status = c.status; last.end = Math.max(last.end, c.end); }
      else merged.push({ start: c.start, end: c.end, status: c.status });
    }
    for (const m of merged) {
      html += esc(text.slice(pos, m.start)) + `<span class="cite ${m.status}">${esc(text.slice(m.start, m.end))}</span>`;
      pos = m.end;
    }
    html += esc(text.slice(pos));
    $("#annot").innerHTML = html || '<span style="color:var(--gray)">Annotated text appears here.</span>';
    const f = r.citations.map((c) => `<div class="find"><div class="stamp ${c.status}">${STAMP[c.status]}</div>
      <div><div class="what">${esc(c.text.trim())}${c.actInferred ? ' <span style="color:var(--gray)">(act inferred)</span>' : ""}</div>
      <div class="msg">${esc(c.message)}</div></div></div>`).join("");
    const v = { clean: ["var(--green)", "VERDICT: CLEAN"], outdated: ["var(--amber)", "VERDICT: CITES REPEALED LAW"], wrong: ["var(--red)", "VERDICT: WRONG CITATION"] }[r.verdict];
    $("#findings").innerHTML = (f || '<p class="note">No statute citations found.</p>') +
      (r.citations.length ? `<div class="verdict" style="color:${v[0]}">${v[1]}</div>` : "");
  }
  const rank = (s) => ({ carryover: 5, nonexistent: 5, stale: 3, omitted: 3, temporal: 3, unknown_act: 1 }[s] || 0);
  $("#input").addEventListener("input", run);
  $("#input").value = EX[0][1];
  run();

  // ---------------------------------------------------------------- lookup
  const ALIAS = { ipc: "IPC", crpc: "CRPC", "cr.p.c": "CRPC", "cr.p.c.": "CRPC", evidence: "IEA", iea: "IEA", bns: "BNS", bnss: "BNSS", bsa: "BSA" };
  function lookup(q) {
    q = q.trim();
    if (!q) return "";
    let m = q.match(/^([a-z.]+(?:\s+act)?)?\s*(?:section\s*)?(\d{1,3}[a-z]{0,2})$/i);
    if (!m) return '<p class="note">Type an act and a section, e.g. “IPC 420”.</p>';
    const num = m[2].toUpperCase();
    const acts = m[1] ? [ALIAS[m[1].toLowerCase().replace(/\s+act$/, "")] || m[1].toUpperCase()] : ["IPC", "CRPC", "IEA", "BNS", "BNSS", "BSA"];
    const card = (sid, cls) => {
      const s = Sanhita.section(sid);
      return `<div class="sec ${cls}"><div class="id">${Sanhita.lab(sid)}</div><div class="h">${esc(s.h)}</div><div class="t">${esc(s.t)}</div></div>`;
    };
    let html = "";
    for (const a of acts) {
      const sid = `${a}:${num}`;
      if (!Sanhita.section(sid)) continue;
      if (["IPC", "CRPC", "IEA"].includes(a)) {
        const succ = Sanhita.successors(sid);
        if (!succ.length || !succ.some((s) => s.to))
          html += `<div class="lk-card">${card(sid, "old")}<div class="arrow">→</div><div class="sec"><div class="id" style="color:var(--red)">Omitted</div><div class="h">No counterpart in the new code.</div></div></div>`;
        for (const s of succ.filter((s) => s.to))
          html += `<div class="lk-card">${card(sid, "old")}<div class="arrow">→<div class="rel">${s.rel}</div></div>${card(s.to, "")}</div>`;
      } else {
        const prev = statutes.new_to_old[sid] || [];
        for (const s of prev)
          html += `<div class="lk-card">${s.from ? card(s.from, "old") : '<div class="sec old"><div class="id">New</div><div class="h">No predecessor</div></div>'}<div class="arrow">→<div class="rel">${s.rel}</div></div>${card(sid, "")}</div>`;
        if (!prev.length) html += `<div class="lk-card"><div></div><div></div>${card(sid, "")}</div>`;
      }
    }
    return html || `<p class="note">No section ${esc(num)} in ${acts.join(", ")}.</p>`;
  }
  $("#lk").addEventListener("input", (e) => ($("#lkOut").innerHTML = lookup(e.target.value)));
  $("#lk").value = "IPC 302";
  $("#lkOut").innerHTML = lookup("IPC 302");

  if (!R) return;
  // ---------------------------------------------------------------- hero stats
  $("#heroStats").innerHTML = R.hero.map((h) => `<div class="stat"><b>${h.v}</b><span>${h.l}</span></div>`).join("");
  $("#benchNote").innerHTML = R.bench_note;
  // ---------------------------------------------------------------- bars
  const COLORS = { correct: "var(--green)", stale: "var(--amber)", carryover: "var(--red)", wrong: "var(--plum)", none: "#c9c1ae", wrong_code: "var(--plum)" };
  function bars(el, task) {
    const rows = R.models.filter((m) => m.tasks[task]).sort((a, b) => (b.tasks[task].correct || 0) - (a.tasks[task].correct || 0));
    el.innerHTML = rows.map((m) => {
      const t = m.tasks[task];
      const segs = ["correct", "carryover", "stale", "wrong", "none"].map((k) =>
        `<span style="width:${(t[k] || 0) * 100}%;background:${COLORS[k]}" title="${k}: ${Math.round((t[k] || 0) * 100)}%"></span>`).join("");
      return `<div class="row"><div class="name">${esc(m.label)}</div><div class="track">${segs}</div><div class="val">${Math.round((t.correct || 0) * 100)}%</div></div>`;
    }).join("");
  }
  bars($("#chartCurrent"), "current");
  bars($("#chartScenario"), "scenario");
  const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
  $("#tblConvert").innerHTML = `<table><tr><th>Model</th><th>Correct</th><th>Gave old number</th></tr>` +
    R.models.filter((m) => m.tasks.convert).map((m) => `<tr><td>${esc(m.label)}</td><td class="n">${pct(m.tasks.convert.correct || 0)}</td><td class="n">${pct(m.tasks.convert.carryover || 0)}</td></tr>`).join("") + "</table>";
  $("#tblTemporal").innerHTML = `<table><tr><th>Model</th><th>2022 → IPC</th><th>2025 → BNS</th></tr>` +
    R.models.filter((m) => m.tasks.temporal_2022).map((m) => `<tr><td>${esc(m.label)}</td><td class="n">${pct(m.tasks.temporal_2022.correct || 0)}</td><td class="n">${pct((m.tasks.temporal_2025 || {}).correct || 0)}</td></tr>`).join("") + "</table>";
  $("#examplesBad").innerHTML = (R.quotes || []).map((q) => `<div class="quote"><div class="q">${esc(q.model)} · asked: ${esc(q.q)}</div><blockquote>“${esc(q.a)}”</blockquote><div class="q" style="color:var(--green)">${esc(q.truth)}</div></div>`).join("");

  // ---------------------------------------------------------------- lora
  if (R.lora) {
    const L = R.lora;
    const card = (title, keys) => `<div class="lcard"><div class="t">${title}</div>${keys.map(([lbl, k]) => {
      const b = (L.base[k] || {}).correct || 0, a = (L.lora[k] || {}).correct || 0;
      return `<div style="font-size:12px;color:var(--ink2);margin-top:8px">${lbl}</div>
        <div class="lbar"><span>before</span><div class="tr"><span style="width:${b * 100}%;background:var(--gray)"></span></div><b>${pct(b)}</b></div>
        <div class="lbar"><span>after</span><div class="tr"><span style="width:${a * 100}%;background:var(--indigo)"></span></div><b>${pct(a)}</b></div>`;
    }).join("")}</div>`;
    $("#loraChart").innerHTML =
      card("Sections it was trained on", [["Old → new conversion", "convert:trained"], ["“Which section covers…”", "current:trained"]]) +
      card("Sections it never saw", [["Old → new conversion", "convert:heldout"], ["“Which section covers…”", "current:heldout"]]) +
      `<div class="lcard"><div class="t">Side effects</div>
        <div style="font-size:12px;color:var(--ink2);margin-top:8px">2022 offence → still the IPC?</div>
        <div class="lbar"><span>before</span><div class="tr"><span style="width:${((L.base["temporal:2022"] || {}).correct || 0) * 100}%;background:var(--gray)"></span></div><b>${pct((L.base["temporal:2022"] || {}).correct)}</b></div>
        <div class="lbar"><span>after</span><div class="tr"><span style="width:${((L.lora["temporal:2022"] || {}).correct || 0) * 100}%;background:var(--indigo)"></span></div><b>${pct((L.lora["temporal:2022"] || {}).correct)}</b></div>
        <div style="font-size:12px;color:var(--ink2);margin-top:8px">General knowledge (ARC-Easy)</div>
        <div class="lbar"><span>before</span><div class="tr"><span style="width:${(L.arc_base || 0) * 100}%;background:var(--gray)"></span></div><b>${pct(L.arc_base)}</b></div>
        <div class="lbar"><span>after</span><div class="tr"><span style="width:${(L.arc_lora || 0) * 100}%;background:var(--indigo)"></span></div><b>${pct(L.arc_lora)}</b></div></div>` +
      `<p class="note" style="grid-column:1/-1">${L.takeaway || ""}</p>`;
  }

  // ---------------------------------------------------------------- audit
  const A = R.audit;
  $("#auditTbl").innerHTML = `<table><tr><th>Dataset (Hugging Face)</th><th>Downloads</th><th>Examples</th><th>Cite a criminal code</th><th>…only repealed codes, no mention of 2023 law</th></tr>` +
    Object.entries(A.datasets).map(([k, d]) => `<tr><td class="mono">${esc(k)}</td><td class="n">${(d.downloads || 0).toLocaleString()}</td><td class="n">${d.examples.toLocaleString()}</td><td class="n">${d.cite_criminal_code.toLocaleString()}</td>
      <td class="n" style="color:${d.share_of_citing_examples_stale > 0.5 ? "var(--red)" : "var(--green)"};font-weight:700">${d.teach_repealed_as_current.toLocaleString()} (${pct(d.share_of_citing_examples_stale)})</td></tr>`).join("") + "</table>";
  const years = Object.entries(A.supreme_court_by_year);
  const maxv = Math.max(...years.map(([, v]) => v.old + v.new));
  const W = 900, H = 230, bw = W / years.length;
  $("#scChart").innerHTML = `<svg viewBox="0 0 ${W} ${H + 40}" style="width:100%;height:auto">` + years.map(([y, v], i) => {
    const ho = (v.old / maxv) * H, hn = (v.new / maxv) * H, x = i * bw + bw * 0.18, w = bw * 0.64;
    return `<rect x="${x}" y="${H - ho - hn}" width="${w}" height="${ho}" fill="#b9ae95"/><rect x="${x}" y="${H - hn}" width="${w}" height="${hn}" fill="#22386f"/>
      <text x="${x + w / 2}" y="${H + 18}" text-anchor="middle" font-family="IBM Plex Mono" font-size="12" fill="#4a5164">${y}</text>
      ${v.new ? `<text x="${x + w / 2}" y="${H - ho - hn - 6}" text-anchor="middle" font-family="IBM Plex Mono" font-size="11" fill="#22386f">${v.new} new</text>` : ""}`;
  }).join("") + `<text x="0" y="${H + 36}" font-family="Public Sans" font-size="12" fill="#4a5164">■ old codes (IPC/CrPC/IEA)   ■ new codes (BNS/BNSS/BSA)</text></svg>`;
  $("#exN").textContent = R.extractor.strings.toLocaleString();
  $("#exF1").textContent = `precision ${(R.extractor.precision * 100).toFixed(1)}%, recall ${(R.extractor.recall * 100).toFixed(1)}%`;
})();
