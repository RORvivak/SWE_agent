from agent.state import AgentState
from integrations.graphify import build_code_graph
from integrations.obsidian import search_vault


def build_context(state: AgentState) -> AgentState:
    print(f"[CONTEXT] Building code graph and memory context...")

    # Code graph via Graphify (AST-based, zero Claude calls)
    code_graph = build_code_graph(
        roles=state["ticket_roles"],
        epic=state["ticket_epic"],
        problem=state["ticket_body"],
    )
    print(f"[GRAPHIFY] Scanned {len(code_graph['files_scanned'])} files → "
          f"{len(code_graph['nodes'])} nodes, {len(code_graph['edges'])} edges")

    # Memory context via Obsidian vault
    memory_notes = search_vault(
        problem=state["ticket_body"],
        epic=state["ticket_epic"],
        roles=state["ticket_roles"],
        top_k=3,
    )
    print(f"[OBSIDIAN] Retrieved {len(memory_notes)} relevant note(s)")

    return {
        **state,
        "code_graph": code_graph,
        "memory_notes": memory_notes,
    }
