// Parity: run the JS port over the same strings as Python; print JSON lines.
import fs from "fs";
await import("../../docs/sanhita.js");
const S = globalThis.Sanhita;
S.load(JSON.parse(fs.readFileSync(new URL("../../sanhita/data/statutes.json", import.meta.url))));
const lines = fs.readFileSync(0, "utf8").split("\n").filter(Boolean);
for (const l of lines) { const t = JSON.parse(l); const r = S.check(t);
  console.log(JSON.stringify(r.citations.map(c => [c.act, c.section, c.status]))); }
