// Personal progress view: renders the achievement DAG for one student.
// Usage: personal.html?student=<handle lowercase, case-insensitive>
// Node states (derived client-side from state.json):
//   accepted (✅, green)  — `✅ accepted` on a claiming issue
//   claimed  (🟡, yellow) — open/redo submission issue exists
//   available(🟦, blue)   — all `requires` accepted, not claimed yet
//   locked   (⚪, grey)   — some `requires` not accepted
// Milestone chain (s1) is shown grey/accepted for context above the tree.
"use strict";

const SW = (c) => `<span class="sw" style="background:${c}"></span>`;
const LEGEND = [
  [SW("#1a7f37") + " accepted", "accepted"],
  [SW("#d4a72c") + " claimed — under review", "claimed"],
  [SW("#409fd3") + " available — prerequisites met", "available"],
  [SW("#d0d7de") + " locked — prerequisites missing", "locked"],
];

function esc(x) {
  return String(x).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function isAccepted(cells, nid) {
  return cells[nid]?.state === "accepted";
}

function nodeState(cells, node, acceptedSet) {
  if (acceptedSet.has(node.id)) return "accepted";
  const cell = cells[node.id];
  if (cell) return "claimed"; // submission open or changes-requested
  if ((node.requires || []).every(r => acceptedSet.has(r))) return "available";
  return "locked";
}

function mermaidDef(achs, cells, acceptedSet) {
  const styleMap = {
    accepted: "fill:#c6f6d5,stroke:#1a7f37",
    claimed: "fill:#fff3bf,stroke:#d4a72c",
    available: "fill:#dbeafe,stroke:#409fd3",
    locked: "fill:#f1f3f5,stroke:#d0d7de",
  };
  const lines = ["graph TD"];
  const ids = new Set(achs.map(a => a.id));
  for (const n of achs) {
    const st = nodeState(cells, n, acceptedSet);
    const label = `${n.id}\\n${n.points}p`;
    lines.push(`  ${n.id}["${label}"]`);
    lines.push(`  class ${n.id} st_${st}`);
    for (const r of n.requires || []) {
      if (ids.has(r)) lines.push(`  ${r} --> ${n.id}`);
      else lines.push(`  ${r}["${r}"]:::st_locked --> ${n.id}`);
    }
  }
  lines.push("  classDef st_accepted fill:#c6f6d5,stroke:#1a7f37");
  lines.push("  classDef st_claimed fill:#fff3bf,stroke:#d4a72c");
  lines.push("  classDef st_available fill:#dbeafe,stroke:#409fd3");
  lines.push("  classDef st_locked fill:#f1f3f5,stroke:#d0d7de");
  void styleMap;
  return lines.join("\n");
}

async function main() {
  const state = await (await fetch("state.json")).json();
  const achs = state.nodes.filter(n => n.kind === "achievement");
  const miles = state.nodes.filter(n => n.kind === "milestone");

  // student picker
  const who = document.getElementById("who");
  for (const s of state.students) {
    const opt = document.createElement("option");
    opt.value = s.handle.toLowerCase();
    opt.textContent = `${s.name} (${s.handle})`;
    who.append(opt);
  }
  const params = new URLSearchParams(location.search);
  let handle = (params.get("student") || "").toLowerCase();
  if (!state.grid[handle]) handle = state.students[0].handle.toLowerCase();
  who.value = handle;
  who.onchange = () => { location.search = "?student=" + who.value; };
  const student = state.students.find(s => s.handle.toLowerCase() === handle);
  const cells = state.grid[handle] || {};

  document.getElementById("meta").innerHTML =
    `· <a href="${esc(student.fork)}">${esc(student.fork)}</a>` +
    ` · <a href="${esc(student.fork)}/pulls">their PRs</a>` +
    ` · <a href="index.html">group grid</a>`;

  document.getElementById("legend").innerHTML =
    LEGEND.map(([h]) => `<span>${h}</span>`).join("");

  const acceptedSet = new Set(
    Object.entries(cells).filter(([, c]) => c.state === "accepted").map(([nid]) => nid));

  const app = document.getElementById("app");
  if (!achs.length) {
    app.innerHTML = "<p class='err'>No achievement nodes in plan.yaml yet.</p>";
  } else {
    const def = mermaidDef(achs, cells, acceptedSet);
    app.innerHTML = `<pre class="mermaid">${esc(def)}</pre>`;
    const mermaid = (await import("https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs")).default;
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
    await mermaid.run({ nodes: [app.querySelector(".mermaid")] });
  }

  // milestone context row
  const ms = miles.map(m => {
    const st = isAccepted(cells, m.id) ? "✅" : (cells[m.id] ? "🟡" : "⚪");
    return `${st} ${esc(m.id)}`;
  }).join(" · ");

  // per-category points + details table
  const byCat = {};
  const rows = achs.map(a => {
    const st = nodeState(cells, a, acceptedSet);
    const pts = st === "accepted" ? a.points : 0;
    byCat[a.category] = (byCat[a.category] || 0) + pts;
    const cell = cells[a.id];
    const issue = cell ? `<a href="https://github.com/${state.repo}/issues/${cell.issue}">issue</a>` : "";
    const pr = cell?.pr_url ? `<a href="${esc(cell.pr_url)}">PR</a>` : "";
    return `<tr><td>${esc(a.id)}</td><td>${esc(a.title)}</td><td>${esc(a.category)}</td>` +
      `<td>${a.points}</td><td>${st}</td><td>${issue} ${pr}</td></tr>`;
  }).join("");
  const total = Object.values(byCat).reduce((a, b) => a + b, 0);
  const catRow = Object.entries(byCat).sort().map(([c, p]) => `${esc(c)}: <b>${p}</b>`).join(" · ");

  document.getElementById("points").innerHTML =
    `<p class="meta">Semester 1 milestones: ${ms}</p>` +
    `<p>Total: <b>${total}</b> points${catRow ? ` (${catRow})` : ""}</p>` +
    `<table><tr><th>Node</th><th>Title</th><th>Category</th><th>Pts</th><th>State</th><th>Links</th></tr>${rows}</table>`;
}

main().catch(e => {
  document.getElementById("app").innerHTML = `<p class="err">Error: ${esc(e)}</p>`;
});
