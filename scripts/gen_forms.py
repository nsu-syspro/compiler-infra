#!/usr/bin/env python3
"""Generate GitHub issue forms (+ template config) from plan.yaml.

Plan changes are data edits; forms are never hand-edited. Regenerate with:
    python3 scripts/gen_forms.py

Outputs:
  .github/ISSUE_TEMPLATE/config.yml
  .github/ISSUE_TEMPLATE/submit-milestone.yml     (one dropdown, all milestones)
  .github/ISSUE_TEMPLATE/claim-achievement.yml    (only if achievement nodes exist)

The form embeds answers into the issue body as
    ### <label>\n\n<value>\n\n...
that harvest.py parses back — the round-trip contract lives in harvest.py.
"""
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TPL_DIR = HERE.parent / ".github" / "ISSUE_TEMPLATE"


def dropdown_value(node: dict) -> str:
    """Dropdown option string; id is the prefix harvested back by harvest.py."""
    return f"{node['id']} — {node['title']}"


def gen_config() -> str:
    return yaml.safe_dump(
        {
            "blank_issues_enabled": False,
            "contact_links": [
                {
                    "name": "Course materials / questions",
                    "about": "Use the course chat or seminar, not issues here — this repo only tracks submissions.",
                    "url": "https://github.com/nsu-syspro",
                }
            ],
        },
        sort_keys=False,
        allow_unicode=True,
    )


def milestone_form(nodes: list[dict]) -> str:
    return yaml.safe_dump(
        {
            "name": "Submit milestone",
            "description": "Submit a completed milestone (semester 1) for review",
            "title": "Submission: ",
            "labels": ["submitted"],
            "body": [
                {
                    "type": "dropdown",
                    "id": "milestone",
                    "attributes": {
                        "label": "Milestone",
                        "description": "Pick the MOST ADVANCED milestone this PR completes — its prerequisites are approved together with it (code review happens on the PR in YOUR fork)",
                        "options": [dropdown_value(n) for n in nodes],
                    },
                    "validations": {"required": True},
                },
                {
                    "type": "input",
                    "id": "fork-pr",
                    "attributes": {
                        "label": "Fork PR link",
                        "description": "Full URL of the implementation PR in your fork",
                        "placeholder": "https://github.com/<your-handle>/<repo>/pull/<number>",
                    },
                    "validations": {"required": True},
                },
                {
                    "type": "textarea",
                    "id": "evidence",
                    "attributes": {
                        "label": "Evidence (optional)",
                        "description": "Anything the PR does not show by itself: harness pass counts, CI run link, caveats. Leave empty if the PR speaks for itself.",
                        "placeholder": "lexer stage: 42/42 goldens green in CI run <link>",
                    },
                },
                {
                    "type": "checkboxes",
                    "id": "checklist",
                    "attributes": {
                        "label": "Checklist",
                        "options": [
                            {"label": "CI on the linked PR is green", "required": True},
                            {"label": "I am the author of the linked PR and the fork owner", "required": True},
                        ],
                    },
                },
            ],
        },
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )


def achievement_form(nodes: list[dict]) -> str:
    return yaml.safe_dump(
        {
            "name": "Claim achievement",
            "description": "Claim a semester-2 achievement (points-based)",
            "title": "Claim: ",
            "labels": ["submitted"],
            "body": [
                {
                    "type": "dropdown",
                    "id": "achievement",
                    "attributes": {
                        "label": "Achievement",
                        "options": [dropdown_value(n) for n in nodes],
                    },
                    "validations": {"required": True},
                },
                {
                    "type": "input",
                    "id": "fork-pr",
                    "attributes": {
                        "label": "Fork PR link",
                        "description": "Full URL of the implementation PR in your fork",
                    },
                    "validations": {"required": True},
                },
                {
                    "type": "textarea",
                    "id": "evidence",
                    "attributes": {
                        "label": "Evidence (optional)",
                        "description": "Demo output / tests proving the achievement, if not evident from the PR",
                    },
                },
            ],
        },
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )


def main() -> None:
    plan = yaml.safe_load((HERE.parent / "plan.yaml").read_text(encoding="utf-8"))
    nodes = plan["nodes"]
    milestones = [n for n in nodes if n["kind"] == "milestone"]
    achievements = [n for n in nodes if n["kind"] == "achievement"]

    TPL_DIR.mkdir(parents=True, exist_ok=True)
    (TPL_DIR / "config.yml").write_text(gen_config(), encoding="utf-8")
    (TPL_DIR / "submit-milestone.yml").write_text(milestone_form(milestones), encoding="utf-8")
    if achievements:
        (TPL_DIR / "claim-achievement.yml").write_text(achievement_form(achievements), encoding="utf-8")
    elif (TPL_DIR / "claim-achievement.yml").exists():
        (TPL_DIR / "claim-achievement.yml").unlink()

    print(f"wrote config.yml, submit-milestone.yml ({len(milestones)} milestones)"
          + (f", claim-achievement.yml ({len(achievements)} achievements)" if achievements else ""))


if __name__ == "__main__":
    sys.exit(main())
