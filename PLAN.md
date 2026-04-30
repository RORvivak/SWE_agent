# Autonomous Engineering Agent — Complete Flow

## System Overview

An autonomous agent that pulls tickets from Notion, compresses code and memory
context using Graphify and Obsidian, plans with Opus, generates code with Sonnet,
validates locally, then ships a branch + PR and updates the ticket.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SYSTEMS                            │
│                                                                     │
│   Notion DB          Obsidian Vault         Target Git Repo         │
│  (tickets)           (past decisions)       (code to change)        │
└────┬─────────────────────┬──────────────────────┬───────────────────┘
     │                     │                      │
     ▼                     ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LANGGRAPH AGENT                              │
│                                                                     │
│  fetch_ticket → build_context → analyze_plan → generate_code        │
│                                                      │              │
│                                                  validate           │
│                                                      │              │
│                                             apply_and_ship          │
│                                                      │              │
│                                             update_ticket           │
│                                                      │              │
│                                              loop / stop            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Complete Flow Diagram

```
                        ┌─────────────────┐
                        │  START / LOOP   │
                        └────────┬────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │      fetch_ticket      │
                    │  • query Notion DB     │
                    │  • filter status=Ready │
                    │  • parse properties    │
                    └────────────┬───────────┘
                                 │
                    no ticket    │   ticket found
                    ┌────────────┴──────────────┐
                    ▼                           ▼
                  STOP                ┌──────────────────────────────┐
               (no work)             │        build_context          │
                                     │                               │
                                     │  1. Graphify(impacted files)  │
                                     │     → compact JSON graph      │
                                     │     → nodes, edges, snippets  │
                                     │                               │
                                     │  2. Obsidian search(problem)  │
                                     │     → top-3 relevant notes    │
                                     │     → past decisions only     │
                                     │                               │
                                     │  ← zero Claude calls here →  │
                                     └──────────────┬───────────────┘
                                                    │
                                                    ▼
                                     ┌──────────────────────────────┐
                                     │        analyze_plan          │
                                     │                              │
                                     │  MODEL: Claude Opus 4.7      │
                                     │  INPUT:                      │
                                     │   • ticket content           │
                                     │   • Graphify graph (cached)  │
                                     │   • Obsidian notes (cached)  │
                                     │                              │
                                     │  OUTPUT:                     │
                                     │   • problem summary          │
                                     │   • files to modify          │
                                     │   • step-by-step plan        │
                                     │   • risks identified         │
                                     └──────────────┬───────────────┘
                                                    │
                                                    ▼
                                     ┌──────────────────────────────┐
                                     │       generate_code          │
                                     │                              │
                                     │  MODEL: Claude Sonnet 4.6    │
                                     │  INPUT:                      │
                                     │   • plan from Opus           │
                                     │   • graph snippets (cached)  │
                                     │                              │
                                     │  OUTPUT:                     │
                                     │   • code diff per file       │
                                     │   • commit message           │
                                     │   • PR title + description   │
                                     └──────────────┬───────────────┘
                                                    │
                                                    ▼
                                     ┌──────────────────────────────┐
                                     │          validate            │
                                     └──────────────┬───────────────┘
                                                    │
                              SKIP_VALIDATION?      │
                        ┌─────────────────┬─────────┘
                      True              False
                        │                 ▼
                        │      ┌─────────────────────┐
                        │      │    run checks        │
                        │      │  • build/compile     │
                        │      │  • pytest            │
                        │      │  • lint (ruff)       │
                        │      └──────────┬──────────┘
                        │                 │
                        │         PASS    │    FAIL
                        │    ┌────────────┴──────────────┐
                        │    │                           │
                        │    │                      RETRY=True?
                        │    │                ┌──────────┴──────────┐
                        │    │              True                   False
                        │    │                ▼                     │
                        │    │   ┌─────────────────────────┐        │
                        │    │   │   fix (Sonnet 4.6)      │        │
                        │    │   │  INPUT:                 │        │
                        │    │   │   • error output        │        │
                        │    │   │   • cached graph        │        │
                        │    │   │   • original diff       │        │
                        │    │   │  OUTPUT: patched diff   │        │
                        │    │   └────────────┬────────────┘        │
                        │    │                │                     │
                        │    │          run checks again            │
                        │    │          PASS  │  FAIL               │
                        │    │    ┌───────────┴──────┐              │
                        │    │    │                  ▼              ▼
                        │    │    │                STOP ←───────────┘
                        │    │    │          • print failure message
                        │    │    │          • update ticket → Blocked
                        │    │    │          • write error to ticket
                        │    │    │
                        └────┴────┘
                             │
                             ▼
                ┌────────────────────────────┐
                │       apply_and_ship       │
                │  1. create git branch      │
                │     feature/<id>-<slug>    │
                │  2. apply code diff        │
                │  3. commit                 │
                │  4. push branch            │
                │  5. open PR on GitHub      │
                └─────────────┬──────────────┘
                              │
                              ▼
                ┌────────────────────────────┐
                │       update_ticket        │
                │  status  → Done            │
                │  PR URL  → written back    │
                └─────────────┬──────────────┘
                              │
                              ▼
                ┌────────────────────────────┐
                │       LOOP / STOP          │
                │  tickets remaining? → loop │
                │  none left?        → stop  │
                └────────────────────────────┘
```

---

## Node-by-Node Explanation

### 1. `fetch_ticket`
- Connects to Notion API
- Queries the ticket database filtered by `status = Ready`
- Picks the first available ticket
- Parses properties: title, description, impacted areas, priority
- If no ticket found → agent stops cleanly

### 2. `build_context`
**No Claude calls in this node — pure compression.**

**Graphify:**
- Receives impacted file paths extracted from ticket
- Runs Graphify on those files
- Gets back a compact JSON knowledge graph:
  - nodes = functions, classes, modules
  - edges = calls, imports, dependencies
  - snippets = only the relevant lines per node
- Filters the graph to the subgraph relevant to the problem
- Result is far smaller than dumping raw files

**Obsidian:**
- Reads `.md` files from the vault
- Searches for notes relevant to the ticket description
- Returns top-3 matching excerpts only (not full notes)
- Sources: `decisions/`, `patterns/`, `fixes/` folders

### 3. `analyze_plan`
- **Model:** Claude Opus 4.7
- **Cached inputs:** Graphify graph + Obsidian notes (prompt cache)
- **Uncached input:** ticket content (changes per ticket)
- Outputs a structured JSON plan:
  ```json
  {
    "problem": "...",
    "files_to_modify": ["src/auth.py"],
    "plan": ["step1", "step2"],
    "risks": ["..."]
  }
  ```
- Does NOT generate code — plan only

### 4. `generate_code`
- **Model:** Claude Sonnet 4.6
- Receives the Opus plan + cached graph snippets
- Outputs minimal unified diffs per file
- Also outputs commit message, PR title, PR description
- Does NOT call Notion or git — pure code output

### 5. `validate`
Two flags control behaviour:

| Flag | Type | Effect |
|---|---|---|
| `SKIP_VALIDATION` | bool | `True` = skip all checks, go straight to ship |
| `RETRY` | bool | `True` = on failure, call Sonnet once to fix before stopping |

**Check sequence (when not skipped):**
1. Build / compile
2. `pytest` (or project test runner)
3. `ruff` / lint

**On failure paths:**
- `RETRY=False` → stop immediately, write error to Notion ticket
- `RETRY=True` → one Sonnet call with error + cached context → re-run checks
  - If still failing → stop, write error to Notion ticket

### 6. `apply_and_ship`
- Creates git branch: `feature/<ticket-id>-<short-slug>`
- Applies diffs to files
- Commits with generated message
- Pushes branch to remote
- Opens pull request via GitHub API

### 7. `update_ticket`
**On success:**
- Notion status → `Done`
- Writes PR URL to ticket

**On failure (from validate):**
- Notion status → `Blocked`
- Writes formatted error output to ticket description

---

## Claude Call Budget

```
Ticket N:
  Call 1 — Opus 4.7   — analyze + plan           (always)
  Call 2 — Sonnet 4.6 — generate code            (always)
  Call 3 — Sonnet 4.6 — fix after failure        (only if RETRY=True and checks fail)

Minimum: 2 calls / ticket
Maximum: 3 calls / ticket
```

**Prompt caching saves ~80% on Call 2 and Call 3:**
- Graphify graph block → cached
- Obsidian notes block → cached
- Only new content (plan / error text) is billed at full rate

---

## State Schema

```python
class AgentState(TypedDict):
    # Ticket
    ticket_id:         str
    ticket_title:      str
    ticket_body:       str
    impacted_areas:    list[str]

    # Context (built locally, no Claude)
    code_graph:        dict         # Graphify output
    memory_notes:      list[str]    # Obsidian top-3 excerpts

    # Planning (Opus)
    problem:           str
    plan:              list[str]
    files_to_modify:   list[str]
    risks:             list[str]

    # Code (Sonnet)
    code_changes:      list[dict]   # [{file, diff}]
    commit_message:    str
    pr_title:          str
    pr_description:    str

    # Validation
    validation_passed: bool
    failure_message:   str | None

    # Git
    branch_name:       str
    pr_url:            str | None

    # Control
    status:            str          # ready | blocked | done | stopped
```

---

## Flags Reference

```python
# validate.py
SKIP_VALIDATION = False   # True → skip checks, go directly to apply_and_ship
RETRY           = False   # True → one Sonnet fix attempt before stopping
```

---

## Environment Variables

```env
# Notion
NOTION_API_KEY=
NOTION_DATABASE_ID=

# Claude
ANTHROPIC_API_KEY=

# Obsidian
OBSIDIAN_VAULT_PATH=/path/to/vault

# GitHub
GITHUB_TOKEN=
GITHUB_REPO=owner/repo

# Target repo
REPO_PATH=/path/to/local/repo
```

---

## Implementation Phases

| # | Phase | Nodes / Files |
|---|---|---|
| 1 | Skeleton | `state.py`, `graph.py` (stub nodes), `config.py` |
| 2 | Notion | `integrations/notion.py`, `nodes/fetch_ticket.py`, `nodes/update_ticket.py` |
| 3 | Context | `integrations/graphify.py`, `integrations/obsidian.py`, `nodes/build_context.py` |
| 4 | Claude | `nodes/analyze_plan.py` (Opus), `nodes/generate_code.py` (Sonnet) |
| 5 | Validate | `nodes/validate.py` (flags + subprocess) |
| 6 | Ship | `nodes/apply_and_ship.py` (git + PR) |
| 7 | E2E test | real ticket → real PR |
