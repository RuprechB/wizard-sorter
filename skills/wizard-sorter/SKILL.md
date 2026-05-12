---
name: wizard-sorter
description: Onboard users into a durable hybrid file organization system, then plan, sort, move-after-approval, deduplicate, index, and find local files. Use for file cleanup, organizing folders, building a remembered filing system, finding files from that system, or preparing future Google Drive sorting workflows across Claude, ChatGPT, and OpenClaw.
---

# Wizard Sorter

## Rules

Run onboarding unless `WIZARD_SORTER.md` exists and contains usable preferences.

Always dry-run first. Never move, rename, delete, or deduplicate files without explicit approval. Duplicates are review items; do not delete automatically.

Use both memory layers:

- `WIZARD_SORTER.md` for human-readable preferences, taxonomy, exclusions, and corrections.
- `.wizard-sorter/index.json` for machine-readable plans, recent moves, hashes, and search hints.

## Onboarding

Offer these sorting systems and let the user choose or customize:

1. Hybrid recommended: life area/project first, then file type/date/status.
2. Life area/project: Finance, Work, Health, Home, Projects, Personal, Archive.
3. File type: Documents, Images, Videos, Audio, Spreadsheets, Code, Archives.
4. Date: YYYY/MM or YYYY/Quarter.
5. Action state: Inbox, Needs Review, Active, Waiting, Done, Archive.
6. Custom user-defined taxonomy.

Ask for scope, destination folder, excluded folders, move/copy preference, rename preference, dedupe preference, and whether optional light text scanning is allowed.

## Local workflow

Use the CLI from the project root:

```bash
python -m wizard_sorter.cli init --path <destination>
python -m wizard_sorter.cli plan --root <source> --dest <destination> --mode hybrid --dedupe --light-scan --output plan.json
python -m wizard_sorter.cli apply --plan plan.json --yes
```

Show the user the plan before applying.

## Finding files

Read `WIZARD_SORTER.md`, then `.wizard-sorter/index.json`, then search likely folders. Return matches with path, reason, and confidence.

## Google Drive

V1 is local-first. For Drive expansion, prefer agent/tool connection first, then OAuth backend later if the project needs platform-independent Drive access.
