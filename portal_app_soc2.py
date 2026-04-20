
from __future__ import annotations
import json
from io import BytesIO
import pandas as pd
import streamlit as st

from soc2_readiness import load_control_intake, prepare_controls, calculate_soc2_readiness, readiness_band

st.set_page_config(page_title="SOC 2 Readiness Portal", page_icon="🛡️", layout="wide")

DEMO_USER = "admin"
DEMO_PASS = "admin123"

def init_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "readiness" not in st.session_state:
        st.session_state.readiness = None
    if "controls_df" not in st.session_state:
        st.session_state.controls_df = None

def login_view():
    st.title("SOC 2 Readiness Portal")
    st.caption("Upload the SOC 2 intake workbook or a Control Intake CSV to score readiness and review the biggest gaps.")
    with st.form("login_form", clear_on_submit=False):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            if user == DEMO_USER and pwd == DEMO_PASS:
                st.session_state.logged_in = True
                st.success("Signed in.")
                st.rerun()
            else:
                st.error("Invalid credentials.")

def color_for_band(band: str) -> str:
    return {
        "Ready": "#2e7d32",
        "Near Ready": "#f9a825",
        "Developing": "#ef6c00",
        "Not Ready": "#c62828",
    }.get(band, "#455a64")

def metric_card(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div style="padding:16px;border-radius:14px;background:#f7f9fc;border:1px solid #e5e9f0;">
            <div style="font-size:13px;color:#5f6b7a;">{title}</div>
            <div style="font-size:28px;font-weight:700;margin-top:4px;">{value}</div>
            <div style="font-size:12px;color:#7b8794;margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def top_summary(readiness):
    band = readiness["readiness_band"]
    score = readiness["overall_score"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Overall SOC 2 Score", f"{score:.1f}", "Weighted readiness estimate")
    with c2:
        metric_card("Readiness Band", band, "Sales-oriented readiness interpretation")
    with c3:
        metric_card("In-scope Controls", str(readiness["counts"]["in_scope"]), "Controls marked in scope")
    with c4:
        metric_card("High-Priority Gaps", str(readiness["counts"]["missing"]), "Controls scoring below 50")

    st.markdown(
        f"""
        <div style="margin-top:14px;margin-bottom:8px;">
            <div style="font-size:13px;color:#5f6b7a;margin-bottom:6px;">Readiness meter</div>
            <div style="background:#e9eef5;border-radius:12px;height:18px;overflow:hidden;">
                <div style="width:{min(score,100)}%;background:{color_for_band(band)};height:18px;"></div>
            </div>
            <div style="font-size:12px;color:#5f6b7a;margin-top:6px;">Band: <b>{band}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def recommendations_box(readiness):
    st.subheader("Top recommended next actions")
    recs = readiness["recommendations"]
    if not recs:
        st.info("No recommendations yet. Upload a control intake file to begin.")
        return
    for idx, rec in enumerate(recs[:3], start=1):
        st.markdown(
            f"""
            <div style="padding:14px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;margin-bottom:10px;">
                <div style="font-size:13px;color:#9a3412;">Decision {idx}</div>
                <div style="font-size:20px;font-weight:700;">{rec['area']}</div>
                <div style="margin-top:4px;">Current score: <b>{rec['score']:.1f}</b> | Priority: <b>{rec['priority']}</b></div>
                <div style="margin-top:6px;color:#7c2d12;">{rec['recommendation']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

def area_scores_section(readiness):
    st.subheader("Area scores")
    data = pd.DataFrame(
        [{"Control Area": k, "Score": v} for k, v in readiness["area_scores"].items()]
    ).sort_values("Score", ascending=True)
    if data.empty:
        st.info("No area scores yet.")
        return
    st.bar_chart(data.set_index("Control Area"))

def blockers_section(readiness):
    st.subheader("Top blockers")
    gaps = pd.DataFrame(readiness["top_gaps"])
    if gaps.empty:
        st.info("No blockers yet.")
        return
    st.dataframe(gaps, use_container_width=True)

def export_json_button(readiness):
    payload = json.dumps(readiness, indent=2)
    st.download_button(
        "Download readiness summary JSON",
        data=payload,
        file_name="soc2_readiness_summary.json",
        mime="application/json",
    )

def main_view():
    st.title("SOC 2 Readiness Dashboard")
    st.caption("Client-ready scorecards, top blockers, and next actions based on the SOC 2 intake workbook.")

    with st.sidebar:
        st.header("Portal Controls")
        if st.button("Log out"):
            st.session_state.logged_in = False
            st.session_state.readiness = None
            st.session_state.controls_df = None
            st.rerun()

        uploaded = st.file_uploader("Upload workbook or CSV", type=["xlsx", "xls", "csv"])
        if uploaded is not None:
            try:
                raw_df = load_control_intake(uploaded)
                controls_df = prepare_controls(raw_df)
                readiness = calculate_soc2_readiness(controls_df)
                st.session_state.controls_df = controls_df
                st.session_state.readiness = readiness
                st.success("File processed successfully.")
            except Exception as e:
                st.error(f"Could not process file: {e}")

        st.markdown("---")
        st.write("Demo login:")
        st.code("admin / admin123")

    readiness = st.session_state.readiness
    controls_df = st.session_state.controls_df

    if readiness is None:
        st.info("Upload the SOC 2 intake workbook or Control Intake CSV to populate the dashboard.")
        return

    top_summary(readiness)

    c1, c2 = st.columns([1.2, 1])
    with c1:
        area_scores_section(readiness)
    with c2:
        recommendations_box(readiness)

    blockers_section(readiness)

    st.subheader("Control detail")
    if controls_df is not None:
        display_cols = [
            "control_id", "control_area", "control_name", "in_scope", "status",
            "evidence_available", "owner_assigned", "policy_exists", "procedure_exists", "tested_recently",
            "row_score", "priority_hint"
        ]
        st.dataframe(controls_df[display_cols], use_container_width=True, height=320)

    export_json_button(readiness)

def main():
    init_state()
    if not st.session_state.logged_in:
        login_view()
    else:
        main_view()

if __name__ == "__main__":
    main()
