import re
from datetime import date
from pathlib import Path
from typing import Any
import yaml
from config import settings


# Folders to search for relevant notes (in priority order)
SEARCH_FOLDERS = [
    "{project}/architecture",
    "{project}/features",
    "{project}/logs",
    "permanent",
    "graphify/{project}",
]


def search_vault(problem: str, epic: str, roles: list[str], top_k: int = 3) -> list[str]:
    """Return top-k relevant note excerpts following Zettelkasten vault structure."""
    vault = Path(settings.obsidian_vault_path)
    project = settings.obsidian_project_name
    query_terms = _query_terms(problem, epic, roles)

    notes = []
    for folder_template in SEARCH_FOLDERS:
        folder = vault / folder_template.format(project=project)
        if not folder.exists():
            continue
        for md_file in folder.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                frontmatter, body = _parse_frontmatter(content)
                notes.append({
                    "path": str(md_file.relative_to(vault)),
                    "frontmatter": frontmatter,
                    "body": body,
                    "tags": _extract_tags(frontmatter, body),
                })
            except Exception:
                continue

    if not notes:
        return []

    scored = sorted(notes, key=lambda n: _score(n, query_terms), reverse=True)
    return [_format_excerpt(n, query_terms) for n in scored[:top_k] if _score(n, query_terms) > 0]


def write_session_log(state: dict) -> None:
    """Write a post-ticket session log into the vault following /save convention."""
    vault = Path(settings.obsidian_vault_path)
    project = settings.obsidian_project_name
    logs_dir = vault / project / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", state.get("ticket_title", "task").lower()).strip("-")[:40]
    log_file = logs_dir / f"{today}-{slug}.md"

    outcome = "Done" if state.get("status") == "done" else "Blocked"
    pr_line = f"PR: {state.get('pr_url')}" if state.get("pr_url") else ""
    error_block = f"\n## Error\n```\n{state.get('failure_message')}\n```" if state.get("failure_message") else ""

    plan_lines = "\n".join(f"- {s}" for s in state.get("plan", []))
    files_lines = "\n".join(f"- `{f}`" for f in state.get("files_to_modify", []))
    risks_lines = "\n".join(f"- {r}" for r in state.get("risks", [])) or "- None"

    content = f"""---
title: {state.get('ticket_title', '')}
tags: [{project}, {state.get('ticket_epic', '').lower().replace(' ', '-')}, {', '.join(state.get('ticket_roles', []))}]
created: {today}
updated: {today}
status: {outcome.lower()}
type: session-log
ticket-priority: {state.get('ticket_priority', '')}
---

# {state.get('ticket_title', '')}

**Outcome:** {outcome}
**Epic:** {state.get('ticket_epic', '')}
**Phase:** {state.get('ticket_phase', '')}
{pr_line}

## Problem
{state.get('problem', '')}

## Plan
{plan_lines}

## Files Modified
{files_lines}

## Risks
{risks_lines}
{error_block}
"""
    log_file.write_text(content, encoding="utf-8")
    print(f"[OBSIDIAN] Session log written → {log_file.relative_to(vault)}")


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        return fm, match.group(2)
    return {}, content


def _extract_tags(frontmatter: dict, body: str) -> list[str]:
    tags = []
    raw = frontmatter.get("tags", [])
    if isinstance(raw, list):
        tags += [str(t).lower() for t in raw]
    elif isinstance(raw, str):
        tags += [t.strip().lower() for t in raw.split(",")]
    tags += [t.lower() for t in re.findall(r"#(\w+)", body)]
    return tags


def _query_terms(problem: str, epic: str, roles: list[str]) -> list[str]:
    stop = {"the", "and", "for", "with", "that", "this", "from", "have", "will", "should"}
    words = re.findall(r"\b\w{4,}\b", (problem + " " + epic + " " + " ".join(roles)).lower())
    return list({w for w in words if w not in stop})


def _score(note: dict, query_terms: list[str]) -> int:
    text = (note["body"] + " ".join(note["tags"])).lower()
    return sum(1 for term in query_terms if term in text)


def _format_excerpt(note: dict, query_terms: list[str], max_chars: int = 500) -> str:
    paragraphs = [p.strip() for p in note["body"].split("\n\n") if p.strip()]
    best = max(
        paragraphs,
        key=lambda p: sum(1 for t in query_terms if t in p.lower()),
        default="",
    )
    return f"[{note['path']}]\n{best[:max_chars]}"
