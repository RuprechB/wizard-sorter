# Google Drive roadmap

V1 is local files only. Google Drive should come next in two phases.

## Phase 1: agent/tool connection

The AI agent uses its existing Google Drive connection.

Pros:
- Faster to build.
- No backend or token storage for Wizard Sorter.
- Natural fit for Claude/OpenClaw/ChatGPT agents that already expose Drive tools.

Cons:
- Different setup per platform.
- Harder to offer one consistent public app experience.

Required behavior:
- Resolve folder IDs before moves.
- Paginate file lists.
- Treat folder names as non-unique.
- Create missing folders only after approval.
- Move by updating parents.
- Store important folder IDs in `WIZARD_SORTER.md` and `.wizard-sorter/index.json`.

## Phase 2: OAuth backend

Wizard Sorter runs its own OAuth app/API.

Pros:
- More consistent across Claude, ChatGPT, OpenClaw, CLI, and future UI.
- Better public product path.

Cons:
- More security work.
- OAuth consent setup and token storage.
- Needs deployment docs and careful scope choices.

Recommended scopes:
- Start with read-only metadata/content where possible.
- Add write/move scope only when the user enables Drive sorting.
