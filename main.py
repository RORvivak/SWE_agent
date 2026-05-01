from agent.graph import build_graph
from agent.state import AgentState
from integrations.notion import mark_blocked


def main():
    graph = build_graph()

    initial_state: AgentState = {
        "ticket_id": "",
        "ticket_title": "",
        "ticket_body": "",
        "ticket_priority": "",
        "ticket_epic": "",
        "ticket_roles": [],
        "ticket_phase": "",
        "ticket_depends_on": "",
        "ticket_wave": None,
        "graph_context": "",
        "memory_notes": [],
        "problem": "",
        "plan": [],
        "files_to_modify": [],
        "risks": [],
        "code_changes": [],
        "commit_message": "",
        "pr_title": "",
        "pr_description": "",
        "validation_passed": False,
        "failure_message": None,
        "branch_name": "",
        "pr_url": None,
        "status": "ready",
    }

    last_state = initial_state
    try:
        for chunk in graph.stream(initial_state):
            for node_state in chunk.values():
                if isinstance(node_state, dict):
                    last_state = {**last_state, **node_state}
    except Exception as e:
        ticket_id = last_state.get("ticket_id", "")
        if ticket_id:
            error_msg = f"Unhandled exception in agent:\n{type(e).__name__}: {e}"
            print(f"\n[CRASH] {error_msg}")
            print("[CRASH] Resetting ticket to 'Not started'")
            mark_blocked(ticket_id, error_msg, last_state.get("ticket_body", ""))
        raise


if __name__ == "__main__":
    main()
