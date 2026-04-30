# Eng Agent — Autonomous Engineering Agent

An autonomous agent that pulls tickets from Notion, compresses code and memory context
using Graphify and Obsidian, plans with Claude Opus, generates code with Claude Sonnet,
validates locally, then ships a branch + PR and updates the ticket.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                              │
│                                                                         │
│   Notion DB              Obsidian Vault            Target Git Repo      │
│  (tickets)               (Zettelkasten memory)     (code to edit)       │
└────┬─────────────────────────┬──────────────────────────┬──────────────┘
     │                         │                          │
     ▼                         ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH AGENT                               │
│                                                                         │
│   fetch_ticket                                                          │
│       │                                                                 │
│   build_context  ──── Graphify CLI (graph.json) ───── zero Claude      │
│       │          ──── Obsidian vault search      ───── zero Claude      │
│       │                                                                 │
│   analyze_plan   ──── Claude Opus 4.7  ─── ticket + graph + memory     │
│       │                                                                 │
│   generate_code  ──── Claude Sonnet 4.6 ─── plan + snippets            │
│       │                                                                 │
│   validate ─── SKIP_VALIDATION=true ──────────────────────┐            │
│       │                                                    │            │
│    [checks]                                                │            │
│    PASS ──────────────────────────────────────────────────┤            │
│    FAIL ── RETRY=true ──► fix (Sonnet) ── re-check ───────┤            │
│    FAIL ── RETRY=false ─────────────────────────────────┐ │            │
│                                                         │ │            │
│   apply_and_ship  ◄─────────────────────────────────────┘─┘            │
│       │           git branch + commit + push + GitHub PR                │
│       │                                                                 │
│   update_ticket   Notion status + vault session log                     │
│       │                                                                 │
│   END / LOOP                                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How It Works

### 1. Fetch Ticket (`fetch_ticket`)
- Queries Notion for the first `Not started` ticket, ordered by Execution Wave → Priority
- Marks it `In progress` immediately so no other run picks it up

### 2. Build Context (`build_context`) — zero Claude calls
**Graphify:**
- Runs `graphify . --update` on the target repo (SHA256 cache — only changed files)
- Writes Obsidian notes to `vault/graphify/{project}/`
- Reads `graphify-out/graph.json` and filters a subgraph relevant to the ticket's epic + roles

**Obsidian:**
- Searches `{project}/architecture/`, `{project}/features/`, `{project}/logs/`, `permanent/`, `graphify/{project}/`
- Parses YAML frontmatter and inline `#tags`
- Returns top-3 relevant excerpts (500 chars each)

### 3. Analyze & Plan (`analyze_plan`) — Claude Opus 4.7
- Receives: ticket + graph JSON + Obsidian notes
- Graph and memory blocks are **prompt-cached** — retries are cheap
- Outputs structured JSON: `problem`, `plan`, `files_to_modify`, `risks`
- Does NOT generate code — plan only
- If requirements unclear → stops with message, resets ticket to `Not started`

### 4. Generate Code (`generate_code`) — Claude Sonnet 4.6
- Receives: Opus plan + cached graph snippets
- Outputs: unified diffs per file, commit message, PR title, PR description

### 5. Validate (`validate`)
| Flag | Value | Behaviour |
|---|---|---|
| `SKIP_VALIDATION` | `true` | Skip all checks, go straight to ship |
| `SKIP_VALIDATION` | `false` | Run build + pytest + ruff/eslint |
| `RETRY` | `true` | On failure: one Sonnet fix attempt before stopping |
| `RETRY` | `false` | On failure: stop immediately, write error to ticket |

- Snapshots original files before applying diffs
- Rolls back automatically on failure (when RETRY=false)

### 6. Fix (`fix`) — Claude Sonnet 4.6, only when RETRY=true
- Sends validation errors + cached snippets + original diff to Sonnet
- Applies patched diff, re-runs checks
- If still failing → rolls back, marks ticket blocked

### 7. Apply & Ship (`apply_and_ship`)
- Creates git branch: `feature/<ticket-id-slug>`
- Stages changed files, commits, pushes to remote
- Opens GitHub PR with ticket context embedded in body

### 8. Update Ticket (`update_ticket`)
| Outcome | Notion Status | Vault |
|---|---|---|
| Success | `Done` + PR URL | Session log written to `{project}/logs/` |
| Failure | Reset to `Not started` + error in Description | Session log written to `{project}/logs/` |

---

## Claude Call Budget

| Call | Model | Purpose | When |
|---|---|---|---|
| 1 | Opus 4.7 | Analyze ticket + produce plan | Always |
| 2 | Sonnet 4.6 | Generate code diffs | Always |
| 3 | Sonnet 4.6 | Fix validation failure | Only if `RETRY=true` and checks fail |

**Minimum: 2 calls/ticket. Maximum: 3 calls/ticket.**

Prompt caching on graph + memory blocks saves ~80% on retries.

---

## Project Structure

```
eng-agent/
│
├── main.py                         # entrypoint — builds and runs the graph
├── config.py                       # pydantic-settings — loads from .env
├── pyproject.toml                  # dependencies
├── .env.example                    # environment variable template
│
├── scripts/
│   └── setup_vault.sh              # one-time vault folder setup
│
├── agent/
│   ├── state.py                    # AgentState TypedDict
│   ├── graph.py                    # LangGraph DAG — nodes + routing
│   └── nodes/
│       ├── fetch_ticket.py         # Notion fetch + mark In Progress
│       ├── build_context.py        # Graphify + Obsidian, zero Claude
│       ├── analyze_plan.py         # Claude Opus — plan only
│       ├── generate_code.py        # Claude Sonnet — code diffs
│       ├── validate.py             # subprocess checks + rollback
│       ├── fix.py                  # Claude Sonnet — fix on retry
│       ├── apply_and_ship.py       # git branch + commit + push + PR
│       └── update_ticket.py        # Notion write-back + vault session log
│
└── integrations/
    ├── notion.py                   # fetch, mark_in_progress, mark_done, mark_blocked
    ├── graphify.py                 # run graphify CLI, filter subgraph
    └── obsidian.py                 # search vault, write session logs
```

---

## Obsidian Vault Structure

```
~/vault/
├── CLAUDE.md                       # global instructions
├── permanent/                      # consolidated atomic notes (Zettelkasten)
├── inbox/                          # raw capture
├── fleeting/                       # quick temporary notes
├── templates/
│   └── default-note.md
├── logs/                           # global session logs
├── references/
│
├── varzo-ai/                       # one folder per project
│   ├── architecture/
│   │   └── decisions.md            # ADRs — why things were built a certain way
│   ├── pipeline/                   # data flows, API contracts
│   ├── data/                       # schema, data model
│   ├── features/                   # planned/implemented features
│   └── logs/                       # ← agent writes here after every ticket
│       └── 2026-04-30-ticket.md
│
├── chats/
│   ├── code/                       # imported Claude Code conversations
│   └── web/                        # imported Claude Web conversations
│
└── graphify/
    └── varzo-ai/                   # auto-generated by graphify CLI
```

---

## Environment Variables

```env
# Notion
NOTION_API_KEY=                     # from notion.so/my-integrations
NOTION_DATABASE_ID=6414b49db9644262a2f6c4ab2dd0e298

# Claude
ANTHROPIC_API_KEY=

# Obsidian
OBSIDIAN_VAULT_PATH=/path/to/vault
OBSIDIAN_PROJECT_NAME=varzo-ai      # subfolder name inside vault

# GitHub
GITHUB_TOKEN=
GITHUB_REPO=owner/repo

# Target repo (the codebase the agent edits)
REPO_PATH=/path/to/local/repo

# Validation flags
SKIP_VALIDATION=false               # true = skip all checks
RETRY=false                         # true = one Sonnet fix attempt on failure
```

---

## How to Spin Up

### Prerequisites
- Python 3.11+
- `git` and `patch` installed
- Notion integration created and connected to your database
- GitHub personal access token (repo scope)

### Step 1 — Install dependencies

```bash
cd eng-agent
pip install -e .
pip install graphifyy
graphify install
```

### Step 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and fill in all values
```

### Step 3 — Set up Obsidian vault

```bash
source .env
bash scripts/setup_vault.sh
```

This creates the full Zettelkasten folder structure and a starter `decisions.md` for your project.

### Step 4 — Generate the first code graph

```bash
cd $REPO_PATH
graphify . --obsidian --obsidian-dir $OBSIDIAN_VAULT_PATH/graphify/$OBSIDIAN_PROJECT_NAME
```

This scans your codebase, outputs `graphify-out/graph.json`, and populates the vault with graph notes. Future runs use `--update` and only process changed files.

### Step 5 — Run the agent

```bash
cd /path/to/eng-agent
python main.py
```

The agent will:
1. Pick up the first `Not started` ticket from Notion
2. Build context from Graphify + Obsidian
3. Plan with Opus, generate code with Sonnet
4. Validate (or skip if `SKIP_VALIDATION=true`)
5. Push a branch, open a PR, update Notion to `Done`
6. Write a session log to the vault
7. Stop (single ticket per run)

### Step 6 — Optional: rebuild graph on every commit

```bash
cd $REPO_PATH
graphify hook install
```

---

## Notion Database Schema

The agent reads from and writes to these properties:

| Property | Type | Used for |
|---|---|---|
| `Task Name` | title | Ticket title |
| `Description` | rich_text | Problem context sent to Opus |
| `Status` | status | Filter `Not started` → write `Done` |
| `Priority` | select | P0–P3 passed to Opus |
| `Epic` | select | Maps to code area (Authentication, AI Screening, etc.) |
| `Role` | multi_select | Backend/Frontend/AI-ML → file extensions to scan |
| `Phase` | select | MVP / Phase 2 / Phase 3 |
| `Depends On` | rich_text | Constraints passed to Opus |
| `Execution Wave` | number | Ticket ordering |

**Status flow:**
```
Not started → In progress → Done
                         → Not started (on failure, error written to Description)
```
