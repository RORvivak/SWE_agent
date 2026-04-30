import json
import subprocess
from pathlib import Path
from config import settings


def build_code_graph(roles: list[str], epic: str, problem: str) -> dict:
    """
    Run graphify on the target repo, write Obsidian notes to vault,
    then return a filtered subgraph relevant to the ticket.
    """
    repo = Path(settings.repo_path)
    graph_path = repo / "graphify-out" / "graph.json"
    obsidian_out = Path(settings.obsidian_vault_path) / "graphify" / settings.obsidian_project_name

    # Run graphify — only processes files changed since last run (SHA256 cache)
    result = subprocess.run(
        ["graphify", "update", str(repo)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"[GRAPHIFY] Warning: {result.stderr.strip()}")

    if not graph_path.exists():
        print("[GRAPHIFY] graph.json not found — returning empty graph")
        return {"nodes": [], "edges": [], "snippets": [], "files_scanned": []}

    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    # Filter to subgraph relevant to this ticket
    keywords = _keywords(epic, problem)
    filtered = _filter_subgraph(graph, keywords, roles)

    node_count = len(filtered.get("nodes", []))
    edge_count = len(filtered.get("edges", []))
    print(f"[GRAPHIFY] {node_count} relevant nodes, {edge_count} edges from graph")

    return filtered


def _keywords(epic: str, problem: str) -> list[str]:
    import re
    stop = {"the", "and", "for", "with", "that", "this", "from", "have", "will", "should"}
    words = re.findall(r"\b\w{4,}\b", (epic + " " + problem).lower())
    return list({w for w in words if w not in stop})


def _filter_subgraph(graph: dict, keywords: list[str], roles: list[str]) -> dict:
    """Return only nodes/edges relevant to the ticket keywords and roles."""
    role_extensions = {
        "Backend":    [".py"],
        "Frontend":   [".js", ".ts", ".tsx", ".jsx"],
        "AI/ML":      [".py", ".ipynb"],
        "DevOps":     [".yml", ".yaml", ".sh"],
        "Full Stack": [".py", ".js", ".ts", ".tsx", ".jsx"],
    }
    allowed_exts = set()
    for role in roles:
        allowed_exts.update(role_extensions.get(role, [".py"]))

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Score and filter nodes (graph uses source_file + label as keys)
    relevant_ids = set()
    relevant_nodes = []
    for node in nodes:
        file_path = node.get("source_file", "") or node.get("file", "")
        ext = Path(file_path).suffix
        if allowed_exts and ext not in allowed_exts:
            continue
        label = node.get("label", "") or node.get("name", "")
        score = sum(1 for kw in keywords if kw in file_path.lower() or kw in label.lower())
        if score > 0:
            relevant_ids.add(node.get("id"))
            relevant_nodes.append(node)

    # Keep edges where both ends are relevant
    relevant_edges = [
        e for e in edges
        if e.get("source") in relevant_ids or e.get("target") in relevant_ids
    ]

    # Extract code snippets from relevant nodes (if graphify provides them)
    snippets = [
        {
            "file": n.get("source_file", n.get("file")),
            "name": n.get("label", n.get("name")),
            "lines": n.get("source_location", n.get("lines", "")),
            "code": n.get("snippet", ""),
        }
        for n in relevant_nodes
        if n.get("snippet")
    ]

    if not relevant_nodes:
        # New feature — no existing code matches. Return the repo file structure
        # so Opus can decide where to add new files.
        all_files = sorted({
            n.get("source_file", "") or n.get("file", "")
            for n in nodes
            if n.get("source_file") or n.get("file")
        })
        return {
            "nodes": [],
            "edges": [],
            "snippets": [],
            "files_scanned": all_files[:200],
            "repo_structure": all_files[:200],
        }

    return {
        "nodes": relevant_nodes[:50],
        "edges": relevant_edges[:100],
        "snippets": snippets[:20],
        "files_scanned": list({n.get("source_file", n.get("file")) for n in relevant_nodes}),
    }
