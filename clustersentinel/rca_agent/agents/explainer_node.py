"""Explainer node: calls the LLM to generate an RCA narrative and remediation steps."""

from __future__ import annotations
import json
import uuid
from datetime import datetime
import pandas as pd
from langchain_core.messages import SystemMessage, HumanMessage
from clustersentinel.rca_agent.state import RCAState
from clustersentinel.simulator.schemas import RCAReport
from clustersentinel.config import settings


_SYSTEM_PROMPT = """You are an expert HCI infrastructure engineer. You diagnose failures in \
hyperconverged infrastructure clusters by analyzing telemetry data. You explain \
failures clearly and suggest actionable remediation. Be specific about nodes, \
metrics, and timings. Use technical language appropriate for a senior SRE."""


def _build_metric_table(state: RCAState) -> str:
    """Format the last 30 minutes of metrics as a compact table."""
    metrics = state["related_metrics"]
    if not metrics:
        return "No metric history available."
    rows = [
        {
            "timestamp": m.timestamp.strftime("%H:%M:%S"),
            "cpu%": round(m.cpu_usage_pct, 1),
            "mem%": round(m.memory_usage_pct, 1),
            "r_iops": int(m.storage_read_iops),
            "w_iops": int(m.storage_write_iops),
            "r_lat_ms": round(m.storage_read_latency_ms, 2),
            "w_lat_ms": round(m.storage_write_latency_ms, 2),
            "cvm_cpu%": round(m.controller_vm_cpu_pct, 1),
            "net_rx": int(m.network_rx_mbps),
            "disk_mb": int(m.disk_throughput_mbps),
        }
        for m in metrics[-20:]  # last 20 samples = ~10 minutes
    ]
    return pd.DataFrame(rows).to_string(index=False)


def _build_user_prompt(state: RCAState) -> str:
    event = state["anomaly_event"]
    correlated_summary = (
        "\n".join(
            f"- {e.node_id} @ {e.timestamp.strftime('%H:%M:%S')}: "
            f"{e.severity.value} on {', '.join(e.affected_metrics[:3])}"
            for e in state["correlated_events"]
        )
        or "None detected."
    )

    return f"""Context from knowledge base:
{state['kb_context'] or 'Not available.'}

Anomaly detected:
- Node: {event.node_id}
- Time: {event.timestamp.isoformat()}
- Severity: {event.severity.value}
- Affected metrics: {', '.join(event.affected_metrics)}
- Ensemble score: {event.ensemble_score:.3f}

Correlated events in the same time window:
{correlated_summary}

Raw metric trajectory (last ~10 minutes):
{_build_metric_table(state)}

Task:
1. Identify the most likely root cause
2. Explain the causal chain (what triggered what)
3. Assess blast radius (which workloads/nodes are affected)
4. Provide 3–5 specific remediation steps in priority order
5. Estimate time-to-resolution if no action is taken

Respond in this exact JSON format:
{{
  "root_cause": "...",
  "causal_chain": "...",
  "blast_radius": "...",
  "remediation_steps": ["step1", "step2", "step3"],
  "time_to_resolution_estimate": "...",
  "confidence_score": 0.0
}}"""


def _get_llm():
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.llm_max_tokens,
    )


def explainer_node(state: RCAState) -> RCAState:
    """Generate RCA narrative via LLM call."""
    event = state["anomaly_event"]
    try:
        llm = _get_llm()
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=_build_user_prompt(state)),
        ]
        response = llm.invoke(messages)
        raw = response.content.strip()

        # Extract JSON block if wrapped in markdown code fences
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        report = RCAReport(
            id=str(uuid.uuid4()),
            anomaly_event_id=event.id or "",
            timestamp=datetime.utcnow(),
            root_cause=parsed.get("root_cause", ""),
            causal_chain=parsed.get("causal_chain", ""),
            blast_radius=parsed.get("blast_radius", ""),
            remediation_steps=parsed.get("remediation_steps", []),
            time_to_resolution_estimate=parsed.get("time_to_resolution_estimate", "Unknown"),
            confidence_score=float(parsed.get("confidence_score", 0.5)),
            raw_llm_output=response.content,
        )
        return {
            **state,
            "rca_report": report,
            "remediation_steps": report.remediation_steps,
            "confidence_score": report.confidence_score,
            "error": None,
        }
    except Exception as exc:
        return {**state, "rca_report": None, "error": str(exc)}
