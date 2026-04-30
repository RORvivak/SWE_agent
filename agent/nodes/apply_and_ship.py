from pathlib import Path
import git
from github import Github
from agent.state import AgentState
from agent.nodes.validate import _apply_diffs
from config import settings


def apply_and_ship(state: AgentState) -> AgentState:
    repo_path = Path(settings.repo_path)
    repo = git.Repo(repo_path)
    branch = state["branch_name"]

    # If validation was skipped, diffs haven't been applied yet — apply now
    if settings.skip_validation:
        error = _apply_diffs(state["code_changes"], repo_path)
        if error:
            return {
                **state,
                "status": "blocked",
                "failure_message": f"Failed to apply diffs before commit:\n{error}",
            }

    # Create and checkout new branch from current HEAD
    if branch in [b.name for b in repo.branches]:
        repo.git.branch("-D", branch)   # clean up if exists from a prior run
    new_branch = repo.create_head(branch)
    new_branch.checkout()
    print(f"[GIT] Branch: {branch}")

    # Stage only the files we changed
    changed_files = [c["file"] for c in state["code_changes"]]
    repo.index.add(changed_files)
    print(f"[GIT] Staged {len(changed_files)} file(s)")

    # Commit
    repo.index.commit(state["commit_message"])
    print(f"[GIT] Committed: {state['commit_message']}")

    # Push branch
    origin = repo.remote("origin")
    origin.push(refspec=f"{branch}:{branch}", set_upstream=True)
    print(f"[GIT] Pushed {branch}")

    # Open PR
    pr_url = _create_pr(state)
    print(f"[PR] Created: {pr_url}")

    return {**state, "pr_url": pr_url, "status": "done"}


def _create_pr(state: AgentState) -> str:
    gh = Github(settings.github_token)
    repo = gh.get_repo(settings.github_repo)

    body = f"""{state['pr_description']}

---
**Ticket:** {state['ticket_title']}
**Epic:** {state['ticket_epic']}
**Priority:** {state['ticket_priority']}
**Phase:** {state['ticket_phase']}

**Plan:**
{chr(10).join(f'- {step}' for step in state['plan'])}

**Risks:**
{chr(10).join(f'- {r}' for r in state['risks']) or '- None identified'}
"""

    pr = repo.create_pull(
        title=state["pr_title"],
        body=body,
        head=state["branch_name"],
        base=repo.default_branch,
    )
    return pr.html_url
