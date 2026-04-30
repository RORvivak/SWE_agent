from agent.graph import build_graph
from agent.state import AgentState

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
        "code_graph": {},
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

    graph.invoke(initial_state)


if __name__ == "__main__":
    main()
