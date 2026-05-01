from typing import TypedDict


class AgentState(TypedDict):
    # Ticket (from Notion)
    ticket_id: str
    ticket_title: str
    ticket_body: str
    ticket_priority: str        # P0-Critical, P1-High, P2-Medium, P3-Low
    ticket_epic: str            # Authentication, AI Screening, etc.
    ticket_roles: list[str]     # Backend, Frontend, AI/ML, DevOps, Full Stack
    ticket_phase: str           # MVP, Phase 2, Phase 3
    ticket_depends_on: str
    ticket_wave: int | None

    # Context (built locally — zero Claude calls)
    graph_context: str          # graphify query result (~2k tokens)
    memory_notes: list[str]     # Obsidian top-3 excerpts (~400 tokens)

    # Planning (Opus via claude -p)
    problem: str
    plan: list[str]
    files_to_modify: list[str]
    risks: list[str]

    # Code (Sonnet via claude -p)
    code_changes: list[dict]    # [{file, content}]
    commit_message: str
    pr_title: str
    pr_description: str

    # Validation
    validation_passed: bool
    failure_message: str | None

    # Git
    branch_name: str
    pr_url: str | None

    # Control
    status: str                 # ready | done | blocked | stopped
