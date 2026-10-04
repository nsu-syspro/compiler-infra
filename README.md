# Compiler course progress tracker (nsu-syspro)

Submission + progress-tracking infra for the syspro compiler course.

**Students:** to submit a milestone for review, [open a new issue](../../issues/new/choose)
with the matching submission form after your fork PR is ready. Code review stays
on the PR in **your fork**; this repo only tracks progress.

## How it works

- `plan.yaml` — the single source of truth: a DAG of plan nodes
  (semester-1 milestone chain + semester-2 achievement tree).
- Submission = a GitHub Issue created with one of the forms in
  `.github/ISSUE_TEMPLATE/`. Fields are embedded in the issue body by GitHub.
- Acceptance = the `✅ accepted` label applied by the teacher on the submission
  issue (audit trail lives in the issue timeline).
- `scripts/harvest.py` runs hourly (`.github/workflows/harvest.yml`): it reads
  all submission issues, joins them with `students.csv` + `plan.yaml`, and
  regenerates `site/state.json`. The state history committed by this workflow
  is the end-of-semester ledger.
- [Progress grid](https://nsu-syspro.github.io/compiler-status/) — students ×
  milestones, regenerated from `state.json`.
- `scripts/gen_forms.py` regenerates the issue forms and labels from
  `plan.yaml` — plan changes are data edits, never hand-edited forms.
- `.github/workflows/plan-check.yml` validates `plan.yaml` (DAG, unique ids,
  required fields) on every PR touching it.

## Layout

```
students.csv           roster: Name;GitHub handle;Fork URL;Language;Group
plan.yaml              unified plan DAG (milestones + achievements)
scripts/gen_forms.py   plan.yaml -> issue forms + labels
scripts/harvest.py     issues + students.csv + plan.yaml -> site/state.json
scripts/validate.py    plan.yaml schema/DAG checks (used by CI and gen_forms)
site/                  static grid page (GitHub Pages)
```

## Labels

| Label | Meaning |
|---|---|
| `✅ accepted` | teacher-approved submission (manual override — teacher may apply it regardless of harvest state) |
| `🔴 changes-requested` | redo requested; student edits the issue and gets re-reviewed |
| `submitted` | well-formed submission, awaiting review |
| `needs-triage` | malformed submission (bad link, wrong author, …) |

## For maintainers (teacher/TA)

- Edit `plan.yaml` for any plan change; CI validates it; run
  `scripts/gen_forms.py` (or let the workflow) to refresh forms.
- Accept a submission by applying `✅ accepted` to its issue, then **close the
  issue** (keeps the issues list short; closed issues keep counting on the
  grid). Accepting the most-advanced milestone of a chain approves its
  prerequisites too (cascade, derived by harvest).
- Redo = `🔴 changes-requested` + comment; the student edits the issue and
  you re-check. Only the teacher closes an accepted issue.
- The harvest workflow commits `state.json` snapshots to `gh-pages`-served
  history; do not rewrite that history.
