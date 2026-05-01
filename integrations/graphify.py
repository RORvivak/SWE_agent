import subprocess
from pathlib import Path
from config import settings


def refresh_graph() -> None:
    """Re-extract changed files and update graph.json (no LLM needed)."""
    repo = Path(settings.repo_path)
    result = subprocess.run(
        ["graphify", "update", str(repo)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[GRAPHIFY] Warning: {result.stderr.strip()}")
    else:
        print(f"[GRAPHIFY] {result.stdout.strip().splitlines()[-1]}")


def query_graph(query: str, budget: int = 2000) -> str:
    """BFS traversal of graph.json — returns at most `budget` tokens of relevant context."""
    graph_path = Path(settings.repo_path) / "graphify-out" / "graph.json"
    if not graph_path.exists():
        print("[GRAPHIFY] graph.json not found — skipping query")
        return ""
    result = subprocess.run(
        ["graphify", "query", query, "--budget", str(budget), "--graph", str(graph_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[GRAPHIFY] Query warning: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()
