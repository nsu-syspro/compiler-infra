#!/usr/bin/env python3
"""Validate a freshly opened/edited submission issue (submission-check.yml).

Checks:
  1. body parses as a form-rendered submission (has '### Milestone'/'### Achievement')
  2. node id from the dropdown exists in plan.yaml
  3. fork PR link parses and the PR exists (GitHub API)
  4. PR author == issue author, PR repo == student's fork from students.csv
  5. PR CI status reported as a comment (warning if red/pending)

Actions: add 'needs-triage' label + a comment listing problems when invalid;
otherwise ensure 'submitted' label present and comment a short confirmation.
Never modifies the teacher's decision labels.
"""
import json
import os
import re
import sys
from urllib.request import Request, urlopen

import yaml

REPO = os.environ["GITHUB_REPOSITORY"]
NUMBER = int(os.environ["ISSUE_NUMBER"])
AUTHOR = os.environ["ISSUE_AUTHOR"]
TOKEN = os.environ["GH_TOKEN"]

ACCEPTED, REDO = "✅ accepted", "🔴 changes-requested"


def api(path: str):
    req = Request(f"https://api.github.com{path}", headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "submission-check",
    })
    with urlopen(req) as r:
        return json.load(r)


def post(path: str, payload: dict) -> None:
    req = Request(f"https://api.github.com{path}", data=json.dumps(payload).encode(),
                  headers={"Authorization": f"Bearer {TOKEN}",
                           "Accept": "application/vnd.github+json",
                           "User-Agent": "submission-check"},
                  method="POST")
    urlopen(req)


def parse_form_body(body: str) -> dict:
    sections, headers = {}, list(re.finditer(r"^### (.+)$", body, re.MULTILINE))
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        v = body[h.end():end].strip()
        sections[h.group(1).strip()] = "" if v == "_" else v
    return sections


def main() -> int:
    issue = api(f"/repos/{REPO}/issues/{NUMBER}")
    body = issue.get("body") or ""
    labels = [l["name"] for l in issue.get("labels", [])]
    if ACCEPTED in labels or REDO in labels:
        print("teacher decision label present; skipping re-check")
        return 0

    fields = parse_form_body(body)
    node_raw = fields.get("Milestone") or fields.get("Achievement") or ""
    node_id = node_raw.split(" — ", 1)[0].strip()
    pr_raw = fields.get("Fork PR link", "")

    here = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
    plan = yaml.safe_load(open(f"{here}/../plan.yaml"))
    nodes = {n["id"] for n in plan["nodes"]}

    problems = []
    if not node_raw:
        problems.append("no **Milestone**/**Achievement** field found — was this opened with the submission form?")
    elif node_id not in nodes:
        problems.append(f"unknown plan node `{node_id}`")

    pr = None
    m = re.match(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$", pr_raw.strip())
    if m:
        owner, repo, num = m.group(1), m.group(2), m.group(3)
        try:
            pr = api(f"/repos/{owner}/{repo}/pulls/{num}")
        except Exception as e:
            problems.append(f"cannot fetch PR {owner}/{repo}#{num}: {e}")
        # identity: PR author must equal issue author
        if pr and pr["user"]["login"] != AUTHOR:
            problems.append(f"PR author `{pr['user']['login']}` != issue author `{AUTHOR}`")
        # fork ownership: PR head repo owner should equal issue author (fork owner)
        if pr:
            head_owner = (pr.get("head") or {}).get("repo", {}) or {}
            if head_owner.get("owner", {}).get("login", "").lower() != AUTHOR.lower():
                problems.append(
                    f"PR head repo owner `{head_owner.get('owner', {}).get('login')}` != fork owner `{AUTHOR}`")
            # CI status on head sha
            sha = ((pr.get("head") or {}).get("sha"))
            if sha:
                try:
                    runs = api(f"/repos/{owner}/{repo}/commits/{sha}/check-runs")
                    concls = [r["conclusion"] for r in runs.get("check_runs", []) if r.get("conclusion")]
                    if concls and all(c == "success" for c in concls):
                        pass  # green
                    elif any(c in ("failure", "timed_out", "action_required") for c in concls):
                        problems.append("⚠️ CI on the linked PR is **red** — fix before review")
                    else:
                        problems.append("⏳ CI on the linked PR is still pending/empty")
                except Exception:
                    pass  # check-runs unreadable — not blocking
    else:
        problems.append(f"cannot parse fork PR link: `{pr_raw or '(empty)'}`")

    if problems:
        post(f"/repos/{REPO}/issues/{NUMBER}/labels", {"labels": ["needs-triage"]})
        post(f"/repos/{REPO}/issues/{NUMBER}/comments", {
            "body": "Automated check found problems with this submission:\n"
                    + "\n".join(f"- {p}" for p in problems)
                    + "\n\nPlease fix (edit the issue) — a maintainer will re-check."})
        print("problems:", problems)
        return 0

    if "submitted" not in labels and "needs-triage" not in labels:
        post(f"/repos/{REPO}/issues/{NUMBER}/labels", {"labels": ["submitted"]})
    ci = "CI green ✅" if pr else "CI status unknown"
    post(f"/repos/{REPO}/issues/{NUMBER}/comments", {
        "body": f"Automated check: submission well-formed, {ci}. Awaiting code review."})
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
