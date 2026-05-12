from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

try:
    from .core import apply_plan, build_plan, fallback_find, search_index, undo_last_apply, write_index
except ImportError:  # Allows `python wizard_sorter/cli.py ...` during local development.
    from core import apply_plan, build_plan, fallback_find, search_index, undo_last_apply, write_index

MODES = ["hybrid", "life-area", "file-type", "date", "action-state"]

ONBOARDING_TEMPLATE = """# WIZARD_SORTER.md

## Profile
- default_mode: hybrid
- review_mode: ask-per-batch
- default_action: move-after-approval
- content_analysis: metadata + optional light scan
- dedupe: detect by sha256; never delete automatically

## Sorting choices to offer users
1. Hybrid: life area/project, then file type or date. Recommended default.
2. Life area/project: Finance, Work, Health, Home, Projects, Personal, Archive.
3. File type: Documents, Images, Videos, Audio, Spreadsheets, Code, Archives.
4. Date: YYYY/MM or YYYY/Quarter.
5. Action state: Inbox, Needs Review, Active, Waiting, Done, Archive.
6. Custom: user-defined taxonomy and exceptions.

## Scope
### Local roots
- path:
  purpose:
  allowed: true

### Future Google Drive roots
- name:
  folder_id:
  purpose:
  allowed: true

## Exclusions
- never_touch: [.git, node_modules, system folders]
- skip_extensions: []

## Known locations

## Corrections / learned rules
"""

SORTING_CHOICES = {
    "1": ("hybrid", "Hybrid: life area/project, then file type/date/status. Recommended default."),
    "2": ("life-area", "Life area/project: Finance, Work, Health, Home, Projects, Personal, Archive."),
    "3": ("file-type", "File type: Documents, Images, Videos, Audio, Spreadsheets, Code, Archives."),
    "4": ("date", "Date: YYYY/MM or YYYY/Quarter."),
    "5": ("action-state", "Action state: Inbox, Needs Review, Active, Waiting, Done, Archive."),
    "6": ("custom", "Custom: user-defined folders, rules, exclusions, and naming conventions."),
}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def yes_no(prompt: str, default: bool = False) -> bool:
    value = ask(prompt, "y" if default else "n").lower()
    return value in {"y", "yes", "true", "1"}


def render_memory(mode: str, root: str, review_mode: str, light_scan: bool, dedupe: bool, custom_rules: str, exclusions: str) -> str:
    custom_section = f"\n## Custom rules\n{custom_rules}\n" if custom_rules else ""
    return f"""# WIZARD_SORTER.md

## Profile
- default_mode: {mode}
- review_mode: {review_mode}
- default_action: move-after-approval
- content_analysis: metadata{' + optional light scan' if light_scan else ''}
- dedupe: {'detect by sha256; never delete automatically' if dedupe else 'off by default'}

## Sorting choices to offer users
1. Hybrid: life area/project, then file type or date. Recommended default.
2. Life area/project: Finance, Work, Health, Home, Projects, Personal, Archive.
3. File type: Documents, Images, Videos, Audio, Spreadsheets, Code, Archives.
4. Date: YYYY/MM or YYYY/Quarter.
5. Action state: Inbox, Needs Review, Active, Waiting, Done, Archive.
6. Custom: user-defined taxonomy and exceptions.

## Scope
### Local roots
- path: {root}
  purpose: primary sorting source
  allowed: true

### Future Google Drive roots
- name:
  folder_id:
  purpose:
  allowed: false

## Exclusions
- never_touch: [{exclusions or '.git, node_modules, system folders'}]
- skip_extensions: []
{custom_section}
## Known locations

## Corrections / learned rules
"""


def cmd_init(args: argparse.Namespace) -> int:
    dest = Path(args.path).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    memory = dest / "WIZARD_SORTER.md"
    if memory.exists() and not args.force:
        print(f"Exists: {memory}")
        return 1
    memory.write_text(ONBOARDING_TEMPLATE)
    print(f"Created {memory}")
    return 0


def cmd_onboard(args: argparse.Namespace) -> int:
    dest = Path(args.path).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    print("Choose a sorting system:")
    for key, (_, description) in SORTING_CHOICES.items():
        print(f"  {key}. {description}")
    choice = ask("Choice", "1")
    mode = SORTING_CHOICES.get(choice, SORTING_CHOICES["1"])[0]
    custom_rules = ""
    if mode == "custom":
        custom_rules = ask("Describe your custom folder rules")
        mode = "hybrid"
    root = ask("Default local folder to sort", str(Path.home() / "Downloads"))
    review_mode = ask("Review mode (ask-per-batch / ask-per-file)", "ask-per-batch")
    light_scan = yes_no("Allow optional light scan for text-like files?", True)
    dedupe = yes_no("Detect duplicates by SHA-256?", True)
    exclusions = ask("Folders never to touch", ".git, node_modules, system folders")
    memory = dest / "WIZARD_SORTER.md"
    if memory.exists() and not args.force:
        print(f"Exists: {memory}. Use --force to replace it.")
        return 1
    memory.write_text(render_memory(mode, root, review_mode, light_scan, dedupe, custom_rules, exclusions))
    print(f"Created onboarding memory: {memory}")
    return 0


def print_plan_summary(plan: dict, *, max_rows: int = 20) -> None:
    rows = plan.get("plan", [])
    duplicate_count = sum(1 for row in rows if row.get("action") == "duplicate-review")
    low_confidence = sum(1 for row in rows if row.get("confidence", 0) < 0.5)
    warning_count = sum(1 for row in rows if row.get("warnings"))
    print(f"Plan: {len(rows)} files | mode={plan.get('mode')} | duplicates={duplicate_count} | low-confidence={low_confidence} | warnings={warning_count}")
    print("-" * 88)
    for row in rows[:max_rows]:
        source = Path(row["source"]).name
        dest = Path(row["destination"]).parent
        flags = []
        if row.get("action") == "duplicate-review":
            flags.append("DUPLICATE")
        if row.get("confidence", 0) < 0.5:
            flags.append("REVIEW")
        if row.get("warnings"):
            flags.append("WARN")
        flag_text = f" [{' '.join(flags)}]" if flags else ""
        print(f"{row.get('confidence', 0):.2f} {row.get('action')} {source} -> {dest}{flag_text}")
    if len(rows) > max_rows:
        print(f"... {len(rows) - max_rows} more rows omitted")


def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve()
    plan = build_plan(root, dest, mode=args.mode, light_scan=args.light_scan, dedupe=args.dedupe)
    if args.output:
        Path(args.output).write_text(json.dumps(plan, indent=2))
        print(f"Wrote plan: {args.output}")
    if args.summary or args.output:
        print_plan_summary(plan, max_rows=args.max_rows)
    else:
        print(json.dumps(plan, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan).expanduser().resolve()
    plan = json.loads(plan_path.read_text())
    if not args.yes:
        print("Refusing to apply without --yes. Review the plan first, then rerun with --yes.")
        return 2
    duplicate_action = "move-to-review" if args.allow_duplicate_review else args.duplicate_action
    result = apply_plan(plan, operation=args.operation, duplicate_action=duplicate_action)
    index_path = write_index(Path(plan["destination_root"]), plan, result)
    print(json.dumps({"result": result, "index": str(index_path)}, indent=2))
    return 0 if not result["errors"] else 1


def cmd_undo(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    if not args.yes:
        print("Refusing to undo without --yes. Undo moves files back and deletes copies created by copy mode.")
        return 2
    result = undo_last_apply(root)
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 1


def cmd_find(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    results = search_index(root, args.query, limit=args.limit)
    source = "index"
    if not results and args.fallback:
        results = fallback_find(root, args.query, limit=args.limit)
        source = "fallback"
    if args.json:
        print(json.dumps({"source": source, "results": results}, indent=2))
        return 0
    print(f"Found {len(results)} match(es) from {source}.")
    for item in results:
        print(f"- {item.get('destination')} (score {item.get('score')})")
        if item.get("reason"):
            print(f"  {item.get('reason')}")
    return 0 if results else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wizard-sorter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Create WIZARD_SORTER.md onboarding memory")
    init.add_argument("--path", default=".")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    onboard = sub.add_parser("onboard", help="Interactive onboarding for WIZARD_SORTER.md")
    onboard.add_argument("--path", default=".")
    onboard.add_argument("--force", action="store_true")
    onboard.set_defaults(func=cmd_onboard)

    plan = sub.add_parser("plan", help="Create a dry-run sorting plan")
    plan.add_argument("--root", required=True)
    plan.add_argument("--dest", required=True)
    plan.add_argument("--mode", choices=MODES, default="hybrid")
    plan.add_argument("--light-scan", action="store_true", help="Read small text snippets from safe text-like files")
    plan.add_argument("--dedupe", action="store_true", help="Hash files and mark duplicates for review")
    plan.add_argument("--output")
    plan.add_argument("--summary", action="store_true", help="Print a readable review summary")
    plan.add_argument("--max-rows", type=int, default=20)
    plan.set_defaults(func=cmd_plan)

    apply = sub.add_parser("apply", help="Apply a reviewed plan")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--yes", action="store_true", help="Confirm file moves")
    apply.add_argument("--operation", choices=["move", "copy"], default="move", help="Move files or copy them while leaving originals in place")
    apply.add_argument("--duplicate-action", choices=["skip", "move-to-review"], default="skip", help="How to handle duplicate-review rows")
    apply.add_argument("--allow-duplicate-review", action="store_true", help="Deprecated alias for --duplicate-action move-to-review")
    apply.set_defaults(func=cmd_apply)

    undo = sub.add_parser("undo", help="Undo the last apply recorded in .wizard-sorter/index.json")
    undo.add_argument("--root", required=True, help="Sorted destination root containing .wizard-sorter/index.json")
    undo.add_argument("--yes", action="store_true", help="Confirm undo")
    undo.set_defaults(func=cmd_undo)

    find = sub.add_parser("find", help="Find files from .wizard-sorter/index.json, with optional fallback path search")
    find.add_argument("query")
    find.add_argument("--root", required=True, help="Sorted destination root containing .wizard-sorter/index.json")
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--fallback", action="store_true", help="Search file paths if the index has no matches")
    find.add_argument("--json", action="store_true")
    find.set_defaults(func=cmd_find)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
