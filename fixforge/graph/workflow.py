from langgraph.graph import StateGraph, END
from core.state import AgentState
from graph.nodes import (
    planner_node, retriever_node, diagnoser_node, fixer_node, 
    verifier_node, confidence_node, reporter_node
)

def build_graph():
    """
    LangGraph Cyclic Orchestration workflow
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("diagnoser", diagnoser_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("confidence", confidence_node)
    workflow.add_node("reporter", reporter_node)
    
    # Define primary linear flow
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "diagnoser")
    workflow.add_edge("diagnoser", "fixer")
    workflow.add_edge("fixer", "verifier")
    
    # Conditional edge after verification
    def should_continue(state: AgentState):
        if state.get("test_passed", False):
            return "confidence"
        elif state.get("retry_count", 0) < 3:
            return "fixer"
        else:
            # Route to Confidence Engine (low confidence band) -> Reporter
            return "confidence"
            
    workflow.add_conditional_edges(
        "verifier",
        should_continue,
        {
            "confidence": "confidence",
            "fixer": "fixer"
        }
    )
    
    # Final reporting
    workflow.add_edge("confidence", "reporter")
    workflow.add_edge("reporter", END)
    
    return workflow.compile()
