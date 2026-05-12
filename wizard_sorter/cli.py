from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .core import apply_plan, build_plan, write_index
except ImportError:  # Allows `python wizard_sorter/cli.py ...` during local development.
    from core import apply_plan, build_plan, write_index

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


def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve()
    plan = build_plan(root, dest, mode=args.mode, light_scan=args.light_scan, dedupe=args.dedupe)
    if args.output:
        Path(args.output).write_text(json.dumps(plan, indent=2))
        print(f"Wrote plan: {args.output}")
    else:
        print(json.dumps(plan, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan).expanduser().resolve()
    plan = json.loads(plan_path.read_text())
    if not args.yes:
        print("Refusing to apply without --yes. Review the plan first, then rerun with --yes.")
        return 2
    result = apply_plan(plan, allow_duplicate_review=args.allow_duplicate_review)
    index_path = write_index(Path(plan["destination_root"]), plan, result)
    print(json.dumps({"result": result, "index": str(index_path)}, indent=2))
    return 0 if not result["errors"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wizard-sorter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Create WIZARD_SORTER.md onboarding memory")
    init.add_argument("--path", default=".")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    plan = sub.add_parser("plan", help="Create a dry-run sorting plan")
    plan.add_argument("--root", required=True)
    plan.add_argument("--dest", required=True)
    plan.add_argument("--mode", choices=MODES, default="hybrid")
    plan.add_argument("--light-scan", action="store_true", help="Read small text snippets from safe text-like files")
    plan.add_argument("--dedupe", action="store_true", help="Hash files and mark duplicates for review")
    plan.add_argument("--output")
    plan.set_defaults(func=cmd_plan)

    apply = sub.add_parser("apply", help="Apply a reviewed plan")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--yes", action="store_true", help="Confirm file moves")
    apply.add_argument("--allow-duplicate-review", action="store_true", help="Move duplicate-review rows instead of skipping them")
    apply.set_defaults(func=cmd_apply)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
