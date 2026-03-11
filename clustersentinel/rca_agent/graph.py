"""LangGraph StateGraph definition for the RCA agent.

Flow: START → detector → correlator → kb_retrieval → explainer → feedback → END
"""

from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from clustersentinel.rca_agent.state import RCAState
from clustersentinel.rca_agent.agents.detector_node import detector_node
from clustersentinel.rca_agent.agents.correlator_node import correlator_node
from clustersentinel.rca_agent.agents.explainer_node import explainer_node
from clustersentinel.rca_agent.agents.feedback_node import feedback_node
from clustersentinel.rca_agent.knowledge_base.loader import retrieve_context
from clustersentinel.simulator.schemas import AnomalyEvent


def kb_retrieval_node(state: RCAState) -> RCAState:
    """Retrieve relevant KB passages from ChromaDB based on event context."""
    event = state["anomaly_event"]
    query = (
        f"HCI failure on node {event.node_id} affecting "
        f"{', '.join(event.affected_metrics[:4])} with severity {event.severity.value}"
    )
    kb_context = retrieve_context(query)
    return {**state, "kb_context": kb_context}


def build_graph() -> StateGraph:
    graph = StateGraph(RCAState)
    graph.add_node("detector", detector_node)
    graph.add_node("correlator", correlator_node)
    graph.add_node("kb_retrieval", kb_retrieval_node)
    graph.add_node("explainer", explainer_node)
    graph.add_node("feedback", feedback_node)

    graph.add_edge(START, "detector")
    graph.add_edge("detector", "correlator")
    graph.add_edge("correlator", "kb_retrieval")
    graph.add_edge("kb_retrieval", "explainer")
    graph.add_edge("explainer", "feedback")
    graph.add_edge("feedback", END)

    return graph.compile()


def run_rca(anomaly_event: AnomalyEvent) -> RCAState:
    """Run the full RCA pipeline for a given anomaly event."""
    app = build_graph()
    initial_state: RCAState = {
        "anomaly_event": anomaly_event,
        "related_metrics": [],
        "correlated_events": [],
        "kb_context": "",
        "rca_report": None,
        "remediation_steps": [],
        "confidence_score": 0.0,
        "feedback": None,
        "error": None,
    }
    return app.invoke(initial_state)
