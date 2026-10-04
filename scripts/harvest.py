#!/usr/bin/env python3
"""Harvest submission issues -> site/state.json.

Joins: submission issues (this repo) x students.csv x plan.yaml.
Submission issue body format is fixed by the issue forms (GitHub embeds form
answers into the body as):

    ### <label>

    <value>

Round-trip contract with gen_forms.py:
  * "Milestone" / "Achievement" value is "<id> — <title>"; split on the FIRST
    " — " only (ids never contain em-dashes, titles may).
  * "Fork PR link" value is the URL as pasted by the student.

state.json shape:
  { "generated": iso8601, "students": [...], "nodes": [...], "submissions": [...] }

Each submission carries: student handle, node id, state
  (accepted | changes-requested | open), issue/PR numbers+urls, timestamps.
Also emits a derived per-(student,node) status map for the grid.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

REPO = os.environ.get("GITHUB_REPOSITORY", "nsu-syspro/compiler-infra")
LABEL_ACCEPTED = "✅ accepted"
LABEL_REDO = "🔴 changes-requested"
STATE_ORDER = {LABEL_ACCEPTED: "accepted", LABEL_REDO: "changes-requested"}

SECTION_RE = re.compile(r"^### (.+)$", re.MULTILINE)


def parse_form_body(body: str) -> dict:
    """Parse a form-rendered issue body into {label: value}.

    Values are the trimmed text between this '### label' and the next one,
    with '_' placeholder (empty answer) normalized to ''.
    """
    sections = {}
    headers = list(SECTION_RE.finditer(body))
    for i, h in enumerate(headers):
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        value = body[start:end].strip()
        if value == "_":  # GitHub forms render empty answers as "_"
            value = ""
        sections[h.group(1).strip()] = value
    return sections


def parse_pr_url(url: str):
    """'https://github.com/<owner>/<repo>/pull/<n>' -> (owner, repo, n) | None."""
    m = re.match(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$", url.strip())
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def pick_state(labels: list[str]) -> str:
    for lab, state in STATE_ORDER.items():
        if lab in labels:
            return state
    return "open"


def load_students(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(";")
    idx = {name: i for i, name in enumerate(header)}
    students = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        f = line.split(";")
        handle = f[idx["GitHub handle"]].strip()
        students[handle.lower()] = {
            "name": f[idx["Student"]].strip(),
            "handle": handle,
            "fork": f[idx["Fork repo link"]].strip().rstrip("/"),
            "language": f[idx["Language"]].strip(),
            "group": f[idx["Group"]].strip(),
        }
    return students


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    issues = []
    if token:
        # Called in CI: use the GitHub API via gh CLI if available, else REST via urllib.
        import subprocess

        r = subprocess.run(
            ["gh", "issue", "list", "-R", REPO, "--state", "all", "--limit", "2000",
             "--json", "number,title,body,author,labels,createdAt,updatedAt,url,state"],
            capture_output=True, text=True,
            env={**os.environ, "GH_TOKEN": token},
        )
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            return 1
        issues = json.loads(r.stdout)
    else:
        # Local mode for development: read issues JSON from a file.
        src = os.environ.get("ISSUES_JSON")
        if not src:
            print("Set GITHUB_TOKEN (CI) or ISSUES_JSON=<path> (local dev)", file=sys.stderr)
            return 1
        issues = json.loads(Path(src).read_text(encoding="utf-8"))

    here = Path(__file__).resolve().parent
    plan = yaml.safe_load((here.parent / "plan.yaml").read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in plan["nodes"]}
    students = load_students(here.parent / "students.csv")

    submissions = []
    for issue in issues:
        body = issue.get("body") or ""
        if "###" not in body:  # not a form-rendered issue (e.g. manual) — skip
            continue
        fields = parse_form_body(body)
        milestone_raw = fields.get("Milestone") or fields.get("Achievement") or ""
        node_id = milestone_raw.split(" — ", 1)[0].strip()
        node = nodes.get(node_id)
        pr_raw = fields.get("Fork PR link", "")
        pr = parse_pr_url(pr_raw)
        author = (issue.get("author") or {}).get("login", "")

        problems = []
        if node is None:
            problems.append(f"unknown node id '{node_id}'")
        if pr is None:
            problems.append(f"cannot parse fork PR link '{pr_raw}'")
        student = students.get(author.lower())
        handle = author.lower()
        if student is None:
            problems.append(f"author '{author}' not in students.csv")
        elif pr is not None:
            fork_owner = urlparse(student["fork"]).path.strip("/").split("/")[0]
            if pr[0].lower() != fork_owner.lower():
                problems.append(f"PR owner '{pr[0]}' != fork owner '{fork_owner}'")

        labels = [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]
        submissions.append({
            "issue": issue["number"],
            "issue_url": issue["url"],
            "issue_title": issue["title"],
            "author": author,
            "student": student["name"] if student else None,
            "node": node_id,
            "node_valid": node is not None,
            "pr": {"owner": pr[0], "repo": pr[1], "number": pr[2],
                   "url": pr_raw} if pr else None,
            "state": pick_state(labels),
            "labels": labels,
            "identity_ok": not problems,
            "problems": problems,
            "created_at": issue.get("createdAt"),
            "updated_at": issue.get("updatedAt"),
            "issue_state": issue.get("state"),
        })

    # Derive per-(student, node) grid status: best submission wins
    # accepted > changes-requested > open (issues open; closed issues keep state
    # but a re-submission supersedes).
    grid = {handle: {} for handle in students}
    for s in submissions:
        handle = (s["author"] or "").lower()
        if handle not in grid:
            continue
        cur = grid[handle].get(s["node"])
        rank = {"accepted": 2, "changes-requested": 1, "open": 0}
        if cur is None or rank[s["state"]] >= rank[cur["state"]]:
            grid[handle][s["node"]] = {"state": s["state"], "issue": s["issue"],
                                       "pr_url": s["pr"]["url"] if s["pr"] else None}

    state = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": REPO,
        "nodes": [{"id": nid, "title": n["title"], "kind": n["kind"],
                   "requires": n["requires"], "points": n["points"]}
                  for nid, n in nodes.items()],
        "students": sorted(students.values(), key=lambda s: (s["group"], s["name"])),
        "submissions": sorted(submissions, key=lambda s: (s["node"], s["author"], s["issue"])),
        "grid": {h: {nid: v for nid, v in g.items()} for h, g in grid.items()},
    }

    out = here.parent / "site" / "state.json"
    out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"state.json: {len(submissions)} submissions, {len(students)} students, "
          f"{len(nodes)} nodes -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
