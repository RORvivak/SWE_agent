from agent.state import AgentState
from integrations.notion import mark_done, mark_blocked
from integrations.obsidian import write_session_log


def update_ticket(state: AgentState) -> AgentState:
    # Always write a session log to vault (win or lose)
    write_session_log(state)

    if state["status"] == "done":
        mark_done(state["ticket_id"], state.get("pr_url", ""))
        print(f"\n[DONE] Ticket updated → Done | PR: {state.get('pr_url')}\n")

    elif state["status"] == "blocked":
        mark_blocked(
            state["ticket_id"],
            state.get("failure_message", "Unknown error"),
            state.get("ticket_body", ""),
        )
        print("\n─────────────────────────────────────────")
        print("AGENT STOPPED — Validation Failed")
        print(f"Ticket : {state['ticket_title']}")
        print(f"Branch : {state.get('branch_name', 'N/A')}")
        print(f"\nError  :\n{state.get('failure_message')}")
        print("Ticket reset to 'Not started' with error details.")
        print("─────────────────────────────────────────\n")

    return state
