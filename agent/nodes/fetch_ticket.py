from agent.state import AgentState
from integrations.notion import fetch_next_ticket, mark_in_progress


def fetch_ticket(state: AgentState) -> AgentState:
    ticket = fetch_next_ticket()

    if not ticket:
        print("\n─────────────────────────────────")
        print("No tickets in 'Not started'. Agent stopping.")
        print("─────────────────────────────────\n")
        return {**state, "status": "stopped"}

    print(f"\n[TICKET] {ticket['ticket_title']} ({ticket['ticket_priority']})")

    mark_in_progress(ticket["ticket_id"])

    return {
        **state,
        **ticket,
        "status": "ready",
    }
