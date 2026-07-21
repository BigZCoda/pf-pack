#!/usr/bin/env python3
"""
people.py -- the people-card adapter (the component's shell).
Facet registry: people/facets.json. Scope rule: people cards NEVER push to the
app -- brain-side only.

The machine door to people/ -- no app, module, or agent scrapes card prose directly.

  python skills/people-adapter/people.py --list [--fields skills,contexts,category]
      JSON array of every card's frontmatter facets (the query surface).
      Legacy cards without frontmatter appear with {"name", "has_frontmatter": false}.

  python skills/people-adapter/people.py --get <slug> [--tier shareable|full]
      One card. tier=full -> whole file. tier=shareable (default) -> the STRIP:
      frontmatter + H1 + status strip + Role & Relationship + Background + archetype
      name if present. Candid sections (Key Notes, Status, folds) NEVER leave at
      shareable tier; lines tagged [private] are stripped at EVERY tier.

  python skills/people-adapter/people.py --verify
      Component verifier: cards parse; frontmatter keys are registered in
      people/facets.json (schema-drift protection); categories valid; dated folds
      well-formed; no [private] content inside shareable sections; cards touched
      after the contract date carry frontmatter (legacy cards = warning only).

Stdlib only. Run from anywhere; paths resolve from the script location.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]
PEOPLE = BRAIN / "people"
REGISTRY = PEOPLE / "facets.json"

SHAREABLE_SECTIONS = ["Role & Relationship", "Background"]
PRIVATE_RE = re.compile(r"\[private\]", re.I)
FOLD_HEAD_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\b")
ARCHETYPE_RE = re.compile(r"archetype[:\s]+\**([A-Z][A-Za-z ]{2,30})\**", re.I)
LIST_RE = re.compile(r"^\[(.*)\]$")


def load_registry():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    known = set(reg["base_facets"].keys())
    for pack in reg.get("packs", {}).values():
        known.update(pack.get("facets", {}).keys())
    return reg, known


def parse_frontmatter(text):
    """Minimal YAML subset: key: value, [a, b] lists, {k: v} maps. None if absent."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm, body = {}, text[end + 4:].lstrip("\n")
    for line in text[3:end].strip().splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.split(" #")[0].strip()
        m = LIST_RE.match(val)
        if m:
            fm[key] = [v.strip().strip("'\"") for v in m.group(1).split(",") if v.strip()]
        elif val.startswith("{"):
            fm[key] = val  # keep maps as raw string; adapter consumers re-parse if needed
        else:
            fm[key] = val.strip("'\"")
    return fm, body


def split_sections(body):
    """-> (preamble, [(header, lines)]) splitting on ## headers."""
    pre, sections, current, buf = [], [], None, []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            if current is not None:
                sections.append((current, buf))
            current, buf = m.group(1), []
        elif current is None:
            pre.append(line)
        else:
            buf.append(line)
    if current is not None:
        sections.append((current, buf))
    return pre, sections


def cards():
    return sorted(p for p in PEOPLE.glob("*.md") if p.name != "readme.md")


def strip_private(lines):
    return [l for l in lines if not PRIVATE_RE.search(l)]


def cmd_list(fields):
    out = []
    for p in cards():
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        row = {"slug": p.stem}
        if fm is None:
            row.update({"name": p.stem.replace("-", " ").title(), "has_frontmatter": False})
        else:
            row["has_frontmatter"] = True
            row.update({k: v for k, v in fm.items() if not fields or k in fields or k == "name"})
        out.append(row)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_get(slug, tier):
    p = PEOPLE / f"{slug}.md"
    if not p.exists():
        sys.exit(f"ERROR: no card people/{slug}.md")
    text = p.read_text(encoding="utf-8")
    if tier == "full":
        print("\n".join(strip_private(text.splitlines())))
        return
    fm, body = parse_frontmatter(text)
    pre, sections = split_sections(body)
    out = []
    if fm is not None:
        out.append("---")
        out += [f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v}"
                for k, v in fm.items()]
        out.append("---")
    out += strip_private(pre)  # H1 + status strip live in the preamble
    for header, lines in sections:
        if header in SHAREABLE_SECTIONS:
            out.append(f"## {header}")
            out += strip_private(lines)
    m = ARCHETYPE_RE.search(text)
    if m:
        out.append(f"\n**Archetype:** {m.group(1).strip()} *(name shareable; dimension scores are not)*")
    print("\n".join(out))


def cmd_verify():
    reg, known = load_registry()
    contract_date = datetime.fromisoformat(reg["contract_date"]).timestamp()
    violations, warnings = [], []
    for p in cards():
        text = p.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        rel = f"people/{p.name}"
        if fm is None:
            if p.stat().st_mtime > contract_date:
                warnings.append(f"{rel}: touched after contract date but no frontmatter yet "
                                "(legal -- grows opportunistically; next fold should add it)")
            continue
        for key in fm:
            if key not in known:
                violations.append(f"{rel}: unregistered facet '{key}' (register in people/facets.json or remove)")
        cat = fm.get("category")
        if cat and cat not in reg["categories"]:
            violations.append(f"{rel}: unknown category '{cat}'")
        pre, sections = split_sections(body)
        for header, lines in sections:
            if header in SHAREABLE_SECTIONS and any(PRIVATE_RE.search(l) for l in lines):
                violations.append(f"{rel}: [private] content inside shareable section '{header}' "
                                  "(move it or the strip leaks nothing but the section placement is wrong)")
            fold = FOLD_HEAD_RE.match(f"## {header}")
            if fold:
                try:
                    date.fromisoformat(fold.group(1))
                except ValueError:
                    violations.append(f"{rel}: malformed fold date '## {header}'")
    for v in violations:
        print(f"[VIOLATION] {v}")
    for w in warnings:
        print(f"[warning]   {w}")
    if violations:
        print(f"{len(violations)} VIOLATIONS")
        sys.exit(1)
    print(f"PEOPLE COMPONENT CLEAN ({len(list(cards()))} cards, {len(warnings)} warnings)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--fields", help="comma-separated facet filter for --list")
    ap.add_argument("--get", metavar="SLUG")
    ap.add_argument("--tier", choices=["shareable", "full"], default="shareable")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.list:
        cmd_list([f.strip() for f in args.fields.split(",")] if args.fields else None)
    elif args.get:
        cmd_get(args.get, args.tier)
    elif args.verify:
        cmd_verify()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
