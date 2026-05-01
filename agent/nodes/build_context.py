from agent.state import AgentState
from integrations.graphify import refresh_graph, query_graph
from integrations.obsidian import search_vault


def build_context(state: AgentState) -> AgentState:
    print("[CONTEXT] Building context...")

    refresh_graph()

    graph_context = query_graph(f"{state['ticket_epic']} {state['ticket_body']}")
    print(f"[GRAPHIFY] Query: {len(graph_context.split())} words of relevant context")

    memory_notes = search_vault(
        problem=state["ticket_body"],
        epic=state["ticket_epic"],
        roles=state["ticket_roles"],
        top_k=3,
    )
    print(f"[OBSIDIAN] {len(memory_notes)} relevant note(s)")

    return {
        **state,
        "graph_context": graph_context,
        "memory_notes": memory_notes,
    }
