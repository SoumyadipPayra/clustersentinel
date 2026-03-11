"""Streamlit dashboard — three-panel layout:
  Panel 1: Cluster Health Timeline (anomaly score per node over time)
  Panel 2: Anomaly Heatmap (nodes × metrics)
  Panel 3: RCA Chat Panel (latest report + follow-up Q&A)
"""

from __future__ import annotations
import json
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from clustersentinel.storage.db import init_db, get_session
from clustersentinel.storage import repository as repo
from clustersentinel.simulator.schemas import Severity, FeedbackRecord

st.set_page_config(page_title="ClusterSentinel", layout="wide", page_icon="🛡️")
init_db()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛡️ ClusterSentinel")
    st.caption("AI-powered HCI anomaly detection & RCA")
    lookback_hours = st.slider("Lookback (hours)", 1, 48, 6)
    severity_filter = st.selectbox("Min severity", ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
    st.divider()
    if st.button("🔄 Refresh"):
        st.rerun()


since = datetime.utcnow() - timedelta(hours=lookback_hours)
sev = None if severity_filter == "ALL" else Severity(severity_filter)

with get_session() as _s:
    anomalies = repo.get_anomaly_events(_s, severity=sev, since=since, limit=500)

st.title("Cluster Health Overview")

# ── Panel 1: Timeline ─────────────────────────────────────────────────────────
st.subheader("📈 Anomaly Score Timeline")
if anomalies:
    df_anom = pd.DataFrame([
        {
            "timestamp": a.timestamp,
            "node_id": a.node_id,
            "ensemble_score": a.ensemble_score,
            "severity": a.severity.value,
            "id": a.id,
        }
        for a in anomalies
    ])
    fig = px.line(
        df_anom,
        x="timestamp", y="ensemble_score",
        color="node_id",
        markers=True,
        labels={"ensemble_score": "Anomaly Score", "timestamp": "Time"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.add_hrect(y0=0.65, y1=0.75, fillcolor="yellow", opacity=0.1, line_width=0, annotation_text="MEDIUM")
    fig.add_hrect(y0=0.75, y1=0.90, fillcolor="orange", opacity=0.1, line_width=0, annotation_text="HIGH")
    fig.add_hrect(y0=0.90, y1=1.0,  fillcolor="red",    opacity=0.1, line_width=0, annotation_text="CRITICAL")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No anomalies detected in the selected time window.")

# ── Panel 2: Heatmap ──────────────────────────────────────────────────────────
st.subheader("🌡️ Anomaly Heatmap (Node × Metric)")
if anomalies:
    metric_scores: dict[tuple[str, str], float] = {}
    for a in anomalies:
        for metric in a.affected_metrics:
            key = (a.node_id, metric)
            metric_scores[key] = max(metric_scores.get(key, 0.0), a.ensemble_score)

    nodes = sorted({a.node_id for a in anomalies})
    metrics_all = sorted({m for a in anomalies for m in a.affected_metrics})

    matrix = [[metric_scores.get((node, metric), 0.0) for metric in metrics_all] for node in nodes]

    heatmap_fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=metrics_all,
        y=nodes,
        colorscale="RdYlGn_r",
        zmin=0, zmax=1,
        colorbar=dict(title="Score"),
    ))
    heatmap_fig.update_layout(height=max(200, len(nodes) * 60))
    st.plotly_chart(heatmap_fig, use_container_width=True)

# ── Panel 3: RCA Chat Panel ───────────────────────────────────────────────────
st.divider()
st.subheader("🔍 RCA Report")

if anomalies:
    anomaly_options = {
        f"{a.timestamp.strftime('%H:%M:%S')} | {a.node_id} | {a.severity.value} | score={a.ensemble_score:.2f}": a
        for a in anomalies[:20]
    }
    selected_label = st.selectbox("Select anomaly event", list(anomaly_options.keys()))
    selected_event = anomaly_options[selected_label]

    col1, col2 = st.columns([2, 1])
    with col1:
        st.json({
            "id": selected_event.id,
            "node": selected_event.node_id,
            "severity": selected_event.severity.value,
            "affected_metrics": selected_event.affected_metrics,
            "ensemble_score": selected_event.ensemble_score,
        })

    with col2:
        if st.button("⚡ Trigger RCA"):
            import httpx
            from clustersentinel.config import settings
            try:
                r = httpx.post(
                    f"http://{settings.api_host}:{settings.api_port}/api/v1/rca/trigger",
                    json={"anomaly_id": selected_event.id},
                    timeout=10,
                )
                if r.status_code == 202:
                    st.success("RCA triggered! Check back in a moment.")
                else:
                    st.error(f"Error: {r.text}")
            except Exception as e:
                st.error(f"Could not reach API: {e}")

    # Show most recent RCA report if available
    with get_session() as _s:
        from clustersentinel.storage.models import RCAReportRecord
        from sqlalchemy import select
        stmt = (
            select(RCAReportRecord)
            .where(RCAReportRecord.anomaly_event_id == selected_event.id)
            .order_by(RCAReportRecord.timestamp.desc())
            .limit(1)
        )
        rca_row = _s.execute(stmt).scalar_one_or_none()

    if rca_row:
        st.markdown(f"**Root Cause**: {rca_row.root_cause}")
        st.markdown(f"**Causal Chain**: {rca_row.causal_chain}")
        st.markdown(f"**Blast Radius**: {rca_row.blast_radius}")
        steps = json.loads(rca_row.remediation_steps)
        st.markdown("**Remediation Steps:**")
        for i, step in enumerate(steps, 1):
            st.markdown(f"{i}. {step}")
        st.caption(f"Confidence: {rca_row.confidence_score:.0%} | ETA: {rca_row.time_to_resolution_estimate}")

        # Feedback
        st.markdown("**Was this analysis helpful?**")
        fb_col1, fb_col2 = st.columns(2)
        with fb_col1:
            if st.button("👍 Helpful"):
                with get_session() as _s:
                    repo.save_feedback(_s, FeedbackRecord(
                        rca_report_id=rca_row.id,
                        timestamp=datetime.utcnow(),
                        helpful=True,
                    ))
                st.success("Thanks!")
        with fb_col2:
            if st.button("👎 Not helpful"):
                with get_session() as _s:
                    repo.save_feedback(_s, FeedbackRecord(
                        rca_report_id=rca_row.id,
                        timestamp=datetime.utcnow(),
                        helpful=False,
                    ))
                st.warning("Feedback recorded.")
    else:
        st.info("No RCA report yet for this event. Trigger one above.")
