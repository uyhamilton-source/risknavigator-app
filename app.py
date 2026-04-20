from __future__ import annotations

import json
from io import StringIO
from typing import Dict, Tuple

import pandas as pd
import streamlit as st

from soc2_readiness import (
    calculate_soc2_readiness,
    load_control_intake,
    prepare_controls,
)

st.set_page_config(
    page_title="RiskNavigator SOC 2 Readiness",
    page_icon="🛡️",
    layout="wide",
)

FALLBACK_USER = "admin"
FALLBACK_PASS = "admin123"


def get_credentials() -> Tuple[str, str]:
    """Read credentials from Streamlit secrets if available."""
    try:
        user = st.secrets["auth"]["username"]
        password = st.secrets["auth"]["password"]
        return user, password
    except Exception:
        return FALLBACK_USER, FALLBACK_PASS


def init_state() -> None:
    defaults = {
        "logged_in": False,
        "readiness": None,
        "controls_df": None,
        "source_name": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def color_for_band(band: str) -> str:
    return {
        "Ready": "#15803d",
        "Near Ready": "#ca8a04",
        "Developing": "#ea580c",
        "Not Ready": "#b91c1c",
    }.get(band, "#334155")


def metric_card(title: str, value: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="padding:16px;border-radius:16px;background:#ffffff;border:1px solid #e2e8f0;box-shadow:0 1px 4px rgba(15,23,42,.06);">
            <div style="font-size:13px;color:#64748b;">{title}</div>
            <div style="font-size:28px;font-weight:700;margin-top:4px;color:#0f172a;">{value}</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def login_view() -> None:
    st.title("RiskNavigator™ SOC 2 Readiness")
    st.caption(
        "Upload a SOC 2 control intake file to score readiness, identify blockers, and generate next actions."
    )
    st.info(
        "For deployment, store credentials in `.streamlit/secrets.toml`. Fallback demo login is available for testing."
    )

    expected_user, expected_pass = get_credentials()

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            if username == expected_user and password == expected_pass:
                st.session_state.logged_in = True
                st.success("Signed in.")
                st.rerun()
            else:
                st.error("Invalid credentials.")

    with st.expander("Demo access"):
        st.code(f"{FALLBACK_USER} / {FALLBACK_PASS}")


def render_readiness_header(readiness: Dict) -> None:
    score = readiness["overall_score"]
    band = readiness["readiness_band"]
    cols = st.columns(4)
    with cols[0]:
        metric_card("Overall Score", f"{score:.1f}", "Weighted readiness estimate")
    with cols[1]:
        metric_card("Readiness Band", band, "Client-friendly maturity label")
    with cols[2]:
        metric_card("In-Scope Controls", str(readiness["counts"]["in_scope"]), "Controls marked in scope")
    with cols[3]:
        metric_card("Priority Gaps", str(readiness["counts"]["missing"]), "Controls scoring below 50")

    st.markdown(
        f"""
        <div style="margin-top:8px;">
            <div style="font-size:13px;color:#64748b;margin-bottom:6px;">Readiness meter</div>
            <div style="background:#e2e8f0;border-radius:999px;height:18px;overflow:hidden;">
                <div style="width:{min(score, 100)}%;background:{color_for_band(band)};height:18px;"></div>
            </div>
            <div style="font-size:12px;color:#64748b;margin-top:6px;">Band: <b>{band}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def executive_summary_text(readiness: Dict) -> str:
    band = readiness["readiness_band"]
    score = readiness["overall_score"]
    gaps = readiness["top_gaps"][:3]
    recs = readiness["recommendations"][:3]

    gap_lines = "\n".join(
        f"- {gap['control_id']} ({gap['control_area']}): {gap['control_name']}"
        for gap in gaps
    ) or "- No major blockers identified"

    rec_lines = "\n".join(
        f"- {rec['area']}: {rec['recommendation']}"
        for rec in recs
    ) or "- Continue preparing evidence and walkthroughs"

    return (
        f"Overall SOC 2 readiness is {score:.1f}, which places the organization in the '{band}' band. "
        "This score reflects current control design, assigned ownership, available evidence, and recent testing.\n\n"
        "Top blockers:\n"
        f"{gap_lines}\n\n"
        "Recommended next actions:\n"
        f"{rec_lines}"
    )


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def render_downloads(readiness: Dict, controls_df: pd.DataFrame) -> None:
    st.subheader("Downloads")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download scored controls CSV",
            data=dataframe_to_csv_bytes(controls_df),
            file_name="soc2_scored_controls.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            "Download readiness JSON",
            data=json.dumps(readiness, indent=2),
            file_name="soc2_readiness_summary.json",
            mime="application/json",
        )
    with col3:
        st.download_button(
            "Download executive summary TXT",
            data=executive_summary_text(readiness),
            file_name="soc2_executive_summary.txt",
            mime="text/plain",
        )


def render_dashboard() -> None:
    st.title("RiskNavigator™ SOC 2 Dashboard")
    st.caption("Client-ready readiness scoring, blockers, and recommended next actions.")

    with st.sidebar:
        st.header("Controls")
        if st.button("Log out"):
            st.session_state.logged_in = False
            st.session_state.readiness = None
            st.session_state.controls_df = None
            st.session_state.source_name = None
            st.rerun()

        uploaded = st.file_uploader(
            "Upload Control Intake (.xlsx or .csv)",
            type=["xlsx", "xls", "csv"],
            help="Upload the workbook template or the sample CSV from this repo.",
        )

        if uploaded is not None:
            try:
                raw_df = load_control_intake(uploaded)
                controls_df = prepare_controls(raw_df)
                readiness = calculate_soc2_readiness(controls_df)
                st.session_state.controls_df = controls_df
                st.session_state.readiness = readiness
                st.session_state.source_name = uploaded.name
                st.success("File processed successfully.")
            except Exception as exc:
                st.error(f"Could not process file: {exc}")

        st.markdown("---")
        st.write("Suggested repo entrypoint:")
        st.code("app.py")

    readiness = st.session_state.readiness
    controls_df = st.session_state.controls_df

    if readiness is None or controls_df is None:
        st.info("Upload a SOC 2 control intake workbook or CSV to populate the dashboard.")
        return

    if st.session_state.source_name:
        st.caption(f"Loaded source: {st.session_state.source_name}")

    render_readiness_header(readiness)

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Area Scores")
        area_df = pd.DataFrame(
            [{"Control Area": area, "Score": score} for area, score in readiness["area_scores"].items()]
        ).sort_values("Score", ascending=True)
        if not area_df.empty:
            st.bar_chart(area_df.set_index("Control Area"))
        else:
            st.info("No area scores yet.")

    with right:
        st.subheader("Top Recommended Next Actions")
        for idx, rec in enumerate(readiness["recommendations"][:3], start=1):
            st.markdown(
                f"""
                <div style="padding:14px;border-radius:14px;background:#fff7ed;border:1px solid #fed7aa;margin-bottom:10px;">
                    <div style="font-size:12px;color:#9a3412;">Decision {idx}</div>
                    <div style="font-size:18px;font-weight:700;color:#7c2d12;">{rec['area']}</div>
                    <div style="font-size:13px;margin-top:4px;">Current score: <b>{rec['score']:.1f}</b> | Priority: <b>{rec['priority']}</b></div>
                    <div style="font-size:13px;margin-top:6px;color:#7c2d12;">{rec['recommendation']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.subheader("Top Blockers")
    blockers_df = pd.DataFrame(readiness["top_gaps"])
    if not blockers_df.empty:
        st.dataframe(blockers_df, use_container_width=True, height=260)
    else:
        st.info("No blockers identified.")

    st.subheader("Scored Control Detail")
    display_cols = [
        "control_id",
        "control_area",
        "control_name",
        "in_scope",
        "status",
        "evidence_available",
        "owner_assigned",
        "policy_exists",
        "procedure_exists",
        "tested_recently",
        "row_score",
        "priority_hint",
    ]
    st.dataframe(controls_df[display_cols], use_container_width=True, height=320)

    st.subheader("Executive Summary")
    st.text_area(
        "Generated summary",
        value=executive_summary_text(readiness),
        height=220,
    )

    render_downloads(readiness, controls_df)


def main() -> None:
    init_state()
    if not st.session_state.logged_in:
        login_view()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
