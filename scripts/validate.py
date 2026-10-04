#!/usr/bin/env python3
"""Validate plan.yaml: schema, unique ids, DAG (no cycles, requires resolve).

Exit 0 = valid; exit 1 = problems (printed to stderr).
Used by CI (plan-check.yml) and defensively by gen_forms.py.
"""
import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = ("id", "kind", "track", "title", "points", "requires", "verify", "accept")
KNOWN_KINDS = {"milestone", "achievement"}
KNOWN_TRACKS = {"s1", "s2"}
KNOWN_VERIFY = {"manual-review"}
ALLOWED_EXTRA = {"grammar", "stage", "category"}


def fail(msg: str) -> None:
    print(f"plan.yaml: {msg}", file=sys.stderr)


def validate(path: Path) -> bool:
    ok = True
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        fail(f"YAML parse error: {e}")
        return False
    nodes = (data or {}).get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail("'nodes' must be a non-empty list")
        return False

    seen = {}
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            fail(f"node #{i}: not a mapping")
            ok = False
            continue
        nid = n.get("id")
        if not nid or not isinstance(nid, str):
            fail(f"node #{i}: missing/invalid 'id'")
            ok = False
            continue
        if nid in seen:
            fail(f"node '{nid}': duplicate id (first seen at node #{seen[nid]})")
            ok = False
        seen[nid] = i

        missing = [f for f in REQUIRED_FIELDS if f not in n]
        if missing:
            fail(f"node '{nid}': missing fields {missing}")
            ok = False
        extra = set(n) - set(REQUIRED_FIELDS) - ALLOWED_EXTRA
        if extra:
            fail(f"node '{nid}': unknown fields {sorted(extra)}")
            ok = False

        if n.get("kind") not in KNOWN_KINDS:
            fail(f"node '{nid}': kind must be one of {sorted(KNOWN_KINDS)}")
            ok = False
        if n.get("track") not in KNOWN_TRACKS:
            fail(f"node '{nid}': track must be one of {sorted(KNOWN_TRACKS)}")
            ok = False
        if n.get("verify") not in KNOWN_VERIFY:
            fail(f"node '{nid}': verify must be one of {sorted(KNOWN_VERIFY)}")
            ok = False

        pts = n.get("points")
        if not isinstance(pts, int) or isinstance(pts, bool):
            fail(f"node '{nid}': points must be an integer")
            ok = False
        elif n.get("kind") == "milestone" and pts != 0:
            fail(f"node '{nid}': milestone points must be 0")
            ok = False
        elif n.get("kind") == "achievement" and pts <= 0:
            fail(f"node '{nid}': achievement points must be > 0")
            ok = False

        req = n.get("requires")
        if not isinstance(req, list) or not all(isinstance(r, str) for r in req):
            fail(f"node '{nid}': 'requires' must be a list of ids")
            ok = False

        stage = n.get("stage")
        if stage is not None and not isinstance(stage, str):
            fail(f"node '{nid}': 'stage' must be a string when present")
            ok = False
        grammar = n.get("grammar")
        if grammar is not None and grammar not in range(1, 6):
            fail(f"node '{nid}': 'grammar' must be 1..5 when present")
            ok = False

    # requires resolve + acyclicity via Kahn's algorithm
    ids = set(seen)
    for nid, i in seen.items():
        for r in nodes[i].get("requires", []) or []:
            if r not in ids:
                fail(f"node '{nid}': requires unknown node '{r}'")
                ok = False
    indeg = {nid: 0 for nid in seen}
    dependents = {nid: [] for nid in seen}
    for nid, i in seen.items():
        for r in nodes[i].get("requires", []) or []:
            if r in indeg:
                indeg[nid] += 1
                dependents[r].append(nid)
    queue = [nid for nid, d in indeg.items() if d == 0]
    processed = 0
    while queue:
        nid = queue.pop()
        processed += 1
        for dep in dependents[nid]:
            indeg[dep] -= 1
            if indeg[dep] == 0:
                queue.append(dep)
    if processed != len(seen):
        cyclic = sorted(nid for nid, d in indeg.items() if d > 0)
        fail(f"cycle detected among nodes {cyclic}")
        ok = False

    return ok


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "plan.yaml")
    if not validate(target):
        sys.exit(1)
    print(f"{target}: OK")
