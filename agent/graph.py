from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.fetch_ticket import fetch_ticket
from agent.nodes.update_ticket import update_ticket
from agent.nodes.build_context import build_context
from agent.nodes.analyze_plan import analyze_plan
from agent.nodes.generate_code import generate_code

from agent.nodes.validate import validate
from agent.nodes.fix import fix
from agent.nodes.apply_and_ship import apply_and_ship


# --- routing ---

def route_after_fetch(state: AgentState) -> str:
    return "stopped" if state["status"] == "stopped" else "continue"

def route_after_validate(state: AgentState) -> str:
    from config import settings
    if state["validation_passed"]:
        return "apply"
    if settings.retry:
        return "fix"
    return "blocked"

def route_after_fix(state: AgentState) -> str:
    return "apply" if state["validation_passed"] else "blocked"


# --- graph ---

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("fetch_ticket", fetch_ticket)
    g.add_node("build_context", build_context)
    g.add_node("analyze_plan", analyze_plan)
    g.add_node("generate_code", generate_code)
    g.add_node("validate", validate)
    g.add_node("fix", fix)
    g.add_node("apply_and_ship", apply_and_ship)
    g.add_node("update_ticket", update_ticket)

    g.set_entry_point("fetch_ticket")

    g.add_conditional_edges("fetch_ticket", route_after_fetch, {
        "stopped": END,
        "continue": "build_context",
    })

    g.add_edge("build_context", "analyze_plan")

    g.add_conditional_edges("analyze_plan", lambda s: "stopped" if s["status"] == "stopped" else "continue", {
        "stopped": END,
        "continue": "generate_code",
    })
    g.add_edge("generate_code", "validate")

    g.add_conditional_edges("validate", route_after_validate, {
        "apply":   "apply_and_ship",
        "fix":     "fix",
        "blocked": "update_ticket",
    })

    g.add_conditional_edges("fix", route_after_fix, {
        "apply":   "apply_and_ship",
        "blocked": "update_ticket",
    })

    g.add_edge("apply_and_ship", "update_ticket")
    g.add_edge("update_ticket", END)

    return g.compile()
