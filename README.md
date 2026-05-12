# Wizard Sorter

Wizard Sorter is an AI-assisted file organizer for Claude, ChatGPT, and OpenClaw.

It helps users create a remembered filing system, generate safe dry-run sort plans, move files only after approval, detect duplicates, and later find files quickly from its memory/index.

V1 is local-file first. Google Drive support is planned after the local workflow is solid.

## What it does

- Onboards each user into a file sorting system.
- Offers popular sorting styles and supports custom rules.
- Uses a recommended hybrid default: life area/project first, then file type/date/status.
- Creates dry-run plans before moving anything.
- Moves files only after approval.
- Detects duplicates by SHA-256 and marks them for review.
- Uses metadata by default and optional light text scanning for text-like files.
- Maintains:
  - `WIZARD_SORTER.md` for human-readable filing rules.
  - `.wizard-sorter/index.json` for machine-readable search/index history.

## Sorting systems offered during onboarding

1. **Hybrid recommended**: `Finance/Documents`, `Projects/Example/Code`, `Personal/Images`.
2. **Life area/project**: Finance, Work, Health, Home, Projects, Personal, Archive.
3. **File type**: Documents, Images, Videos, Audio, Spreadsheets, Code, Archives.
4. **Date**: `2026/05`, `2026/Q2`, etc.
5. **Action state**: Inbox, Needs Review, Active, Waiting, Done, Archive.
6. **Custom**: user-defined folders, rules, exclusions, and naming conventions.

## Install for local development

```bash
git clone https://github.com/RuprechB/wizard-sorter.git
cd wizard-sorter
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or run without installing:

```bash
python -m wizard_sorter.cli --help
```

## Quick start

Create the memory file in your destination folder:

```bash
wizard-sorter init --path ~/SortedFiles
```

Generate a dry-run plan:

```bash
wizard-sorter plan \
  --root ~/Downloads \
  --dest ~/SortedFiles \
  --mode hybrid \
  --dedupe \
  --light-scan \
  --output plan.json
```

Review `plan.json`. Then apply after approval:

```bash
wizard-sorter apply --plan plan.json --yes
```

Duplicate rows are skipped by default and must be reviewed manually.

## Safety model

Wizard Sorter is designed to be conservative:

- No moves without approval.
- No deletes in v1.
- Duplicate detection creates review items, not deletion commands.
- Light scan is optional and limited to text-like files.
- Excludes common dangerous folders like `.git`, `node_modules`, virtual envs, and `.wizard-sorter`.

## Claude / OpenClaw skill

Use:

```text
skills/claude-openclaw/SKILL.md
```

Install or copy that folder into your agent's skill system.

## ChatGPT Custom GPT

Use:

```text
references/chatgpt-custom-gpt.md
```

For a Custom GPT with Actions, expose API operations equivalent to:

- `initMemory(destination)`
- `createPlan(root, destination, mode, lightScan, dedupe)`
- `applyPlan(planId, approved)`
- `searchIndex(query)`

Without Actions, ChatGPT can guide users through the CLI and review pasted plans.

## Google Drive plan

Google Drive is planned after local sorting.

Recommended path:

1. Use each agent platform's existing Google Drive connection first.
2. Add a real OAuth backend later if Wizard Sorter becomes a public app/UI.

See `references/google-drive-roadmap.md`.

## Repository layout

```text
wizard_sorter/                 Python CLI and sorting engine
skills/claude-openclaw/        Claude/OpenClaw skill entry point
references/                    ChatGPT instructions and Drive roadmap
examples/                      Example memory and plan files
```

## License

MIT
