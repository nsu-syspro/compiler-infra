#!/usr/bin/env bash
# Idempotently create the decision/automation labels in the infra repo.
# Run once after repo creation (or after label renames). Requires gh auth.
set -euo pipefail
REPO="${1:-nsu-syspro/compiler-infra}"

mk() { # name color description
  gh label create "$1" -R "$REPO" --color "$2" --description "$3" 2>/dev/null \
    || gh label edit "$1" -R "$REPO" --color "$2" --description "$3"
}

mk "✅ accepted"         "0e8a16" "Submission accepted by the teacher (manual override)"
mk "🔴 changes-requested" "d93f0b" "Redo requested — edit the issue and re-submit for review"
mk "submitted"           "fbca04" "Well-formed submission awaiting review (auto)"
mk "needs-triage"        "e99695" "Malformed submission — see bot comment (auto)"
echo "labels ready on $REPO"
