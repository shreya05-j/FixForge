from langgraph.graph import StateGraph, END
from core.state import AgentState
from core.config import settings
from graph.nodes import (
    planner_node, retriever_node, diagnoser_node, fixer_node, 
    verifier_node, confidence_node, reporter_node
)

def build_workflow():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("diagnoser", diagnoser_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("confidence_engine", confidence_node)
    workflow.add_node("reporter", reporter_node)
    
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "diagnoser")
    workflow.add_edge("diagnoser", "fixer")
    workflow.add_edge("fixer", "verifier")
    
    def verification_router(state: AgentState):
        test_passed = state.get("test_results", {}).get("passed", False)
        retries = state.get("retry_count", 0)
        
        if test_passed:
            return "confidence_engine"
        elif retries < settings.MAX_RETRIES:
            return "fixer"
        else:
            return "confidence_engine"
            
    workflow.add_conditional_edges(
        "verifier",
        verification_router,
        {
            "confidence_engine": "confidence_engine",
            "fixer": "fixer"
        }
    )
    
    workflow.add_edge("confidence_engine", "reporter")
    workflow.add_edge("reporter", END)
    
    return workflow.compile()
