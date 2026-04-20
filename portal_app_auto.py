from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
import json
import hashlib
import os
import pandas as pd
import streamlit as st

from risk_engine_auto import analyze

st.set_page_config(page_title="RiskNavigator Automation Portal", page_icon="🛡️", layout="wide")

DEMO_USER = "admin"
DEMO_PASS = "admin123"
BASE_DIR = Path("portal_output_auto")
ASSESS_DIR = BASE_DIR / "assessments"
REGISTRY = BASE_DIR / "assessment_registry.json"
ASSESS_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR.mkdir(exist_ok=True)


def load_registry() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"assessments": []}


def save_registry(data: dict) -> None:
    REGISTRY.write_text(json.dumps(data, indent=2), encoding="utf-8")


def file_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:12]


def metric_card(title: str, value: str, subtitle: str = "", accent: str = "#0f766e"):
    st.markdown(
        f"""
        <div style="padding:16px;border-radius:16px;background:linear-gradient(180deg,#ffffff,#f8fafc);border:1px solid #e2e8f0;box-shadow:0 1px 2px rgba(0,0,0,.04)">
            <div style="font-size:13px;color:#64748b;">{title}</div>
            <div style="font-size:28px;font-weight:700;margin-top:4px;color:{accent}">{value}</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def login_view():
    st.title("RiskNavigator Automation Portal")
    st.caption("Upload client assessment files. The portal auto-runs the risk engine, refreshes the dashboard, and schedules the next reminder.")
    with st.form("login_form"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if user == DEMO_USER and pwd == DEMO_PASS:
                st.session_state.logged_in = True
                st.rerun()
            st.error("Invalid credentials.")


def init_state():
    defaults = {
        "logged_in": False,
        "selected_client": None,
        "refresh_ts": datetime.utcnow().isoformat(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def upsert_assessment_record(client_name: str, contact_email: str, frequency_days: int, src_file: str, output_dir: Path, file_hash: str):
    reg = load_registry()
    now = datetime.utcnow()
    next_due = now + timedelta(days=frequency_days)
    rec = {
        "client_name": client_name,
        "contact_email": contact_email,
        "frequency_days": frequency_days,
        "source_file": src_file,
        "output_dir": str(output_dir),
        "last_run_utc": now.isoformat(),
        "next_due_utc": next_due.isoformat(),
        "file_hash": file_hash,
        "status": "current",
    }
    items = [r for r in reg["assessments"] if r["client_name"] != client_name]
    items.append(rec)
    reg["assessments"] = sorted(items, key=lambda x: x["client_name"].lower())
    save_registry(reg)


def auto_run_upload(client_name: str, contact_email: str, frequency_days: int, uploaded_file):
    content = uploaded_file.read()
    client_dir = ASSESS_DIR / client_name.replace(" ", "_")
    client_dir.mkdir(parents=True, exist_ok=True)
    source_path = client_dir / "latest_input.csv"
    source_path.write_bytes(content)
    analyze(str(source_path), str(client_dir))
    upsert_assessment_record(client_name, contact_email, frequency_days, str(source_path), client_dir, file_digest(content))
    st.session_state.selected_client = client_name
    st.session_state.refresh_ts = datetime.utcnow().isoformat()


def list_clients():
    reg = load_registry()
    return [r["client_name"] for r in reg.get("assessments", [])]


def get_client_record(client_name: str):
    reg = load_registry()
    for r in reg.get("assessments", []):
        if r["client_name"] == client_name:
            return r
    return None


def upload_and_run_view():
    st.subheader("Upload → auto-run → dashboard refresh")
    with st.form("upload_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            client_name = st.text_input("Client name", placeholder="Sunrise Health Group")
        with c2:
            contact_email = st.text_input("Reminder email", placeholder="ops@example.com")
        with c3:
            frequency_days = st.selectbox("Refresh cadence", [7, 14, 30, 60, 90], index=2)
        uploaded = st.file_uploader("Upload integrated risk CSV", type=["csv"])
        submitted = st.form_submit_button("Upload and run assessment")
        if submitted:
            if not client_name or not uploaded:
                st.error("Client name and CSV file are required.")
            else:
                auto_run_upload(client_name, contact_email, frequency_days, uploaded)
                st.success("Assessment completed. Dashboard refreshed and next reminder scheduled.")
                st.rerun()

    reg = load_registry()
    if reg["assessments"]:
        st.markdown("### Scheduled clients")
        sched = pd.DataFrame(reg["assessments"])
        if not sched.empty:
            view = sched[["client_name", "contact_email", "frequency_days", "last_run_utc", "next_due_utc", "status"]]
            st.dataframe(view, use_container_width=True)


def client_selector():
    clients = list_clients()
    if not clients:
        st.info("No assessments yet. Upload a client CSV first.")
        return None
    default_idx = 0
    if st.session_state.selected_client in clients:
        default_idx = clients.index(st.session_state.selected_client)
    client = st.selectbox("Client workspace", clients, index=default_idx)
    st.session_state.selected_client = client
    return client


def risk_dashboard_view(client_name: str):
    rec = get_client_record(client_name)
    if not rec:
        st.info("Select a client workspace.")
        return
    out_dir = Path(rec["output_dir"])
    report_path = out_dir / "client_risk_report.csv"
    summary_path = out_dir / "client_risk_summary.json"
    if not report_path.exists() or not summary_path.exists():
        st.warning("Assessment outputs are missing for this client.")
        return
    report_df = pd.read_csv(report_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    c1, c2, c3, c4 = st.columns(4)
    top_assets = summary.get("top_10_highest_risk_assets", [])
    top_score = top_assets[0]["risk_score"] if top_assets else 0
    total_loss_low = int(sum(a.get("estimated_loss_low", 0) for a in top_assets))
    total_loss_high = int(sum(a.get("estimated_loss_high", 0) for a in top_assets))
    with c1:
        metric_card("Highest Asset Risk", f"{top_score:.1f}", "Top asset score")
    with c2:
        metric_card("Total Assets", str(summary.get("total_assets", 0)), "Assets assessed")
    with c3:
        metric_card("Low Loss Estimate", f"${total_loss_low:,.0f}", "Top 10 assets")
    with c4:
        metric_card("High Loss Estimate", f"${total_loss_high:,.0f}", "Top 10 assets", accent="#b91c1c")

    st.markdown("### Top 3 decisions")
    decisions = pd.DataFrame(summary.get("top_3_decisions", []))
    st.dataframe(decisions, use_container_width=True)

    a, b = st.columns([1.3, 1])
    with a:
        st.markdown("### Risk by asset")
        chart_df = (
            report_df[["hostname", "risk_score", "criticality"]]
            .drop_duplicates()
            .sort_values("risk_score", ascending=False)
            .head(12)
            .set_index("hostname")
        )
        st.bar_chart(chart_df["risk_score"])
    with b:
        st.markdown("### Risk bands")
        bands = pd.DataFrame(list(summary.get("risk_band_counts", {}).items()), columns=["Band", "Count"]).set_index("Band")
        st.bar_chart(bands)

    st.markdown("### Findings detail")
    filters = st.columns(3)
    with filters[0]:
        priority = st.selectbox("Priority filter", ["All"] + sorted(report_df["remediation_priority"].fillna("").unique().tolist()))
    with filters[1]:
        unit = st.selectbox("Business unit", ["All"] + sorted(report_df["business_unit"].fillna("").unique().tolist()))
    with filters[2]:
        csf = st.selectbox("CSF category", ["All"] + sorted(report_df["csf_category"].fillna("").unique().tolist()))

    filtered = report_df.copy()
    if priority != "All":
        filtered = filtered[filtered["remediation_priority"] == priority]
    if unit != "All":
        filtered = filtered[filtered["business_unit"] == unit]
    if csf != "All":
        filtered = filtered[filtered["csf_category"] == csf]
    st.dataframe(filtered, use_container_width=True, height=320)


def reminders_view():
    st.subheader("Reminder schedule")
    reg = load_registry()
    items = reg.get("assessments", [])
    if not items:
        st.info("No scheduled reminders yet.")
        return
    df = pd.DataFrame(items)
    df["last_run_utc"] = pd.to_datetime(df["last_run_utc"], errors="coerce")
    df["next_due_utc"] = pd.to_datetime(df["next_due_utc"], errors="coerce")
    df["days_until_due"] = (df["next_due_utc"] - pd.Timestamp.utcnow()).dt.days
    st.dataframe(df[["client_name", "contact_email", "frequency_days", "last_run_utc", "next_due_utc", "days_until_due"]], use_container_width=True)

    due = df[df["days_until_due"] <= 3].copy()
    st.markdown("### Due soon")
    if due.empty:
        st.success("No reminders due within 3 days.")
    else:
        st.dataframe(due[["client_name", "contact_email", "next_due_utc", "days_until_due"]], use_container_width=True)

    st.markdown("### Reminder worker")
    st.code("python reminder_worker.py", language="bash")
    st.caption("The worker checks the schedule and writes reminder drafts or sends real emails if SMTP variables are configured.")


def downloads_view(client_name: str):
    rec = get_client_record(client_name)
    if not rec:
        return
    out_dir = Path(rec["output_dir"])
    st.subheader("Downloads")
    for filename in ["client_risk_report.csv", "client_risk_summary.json"]:
        path = out_dir / filename
        if path.exists():
            st.download_button(f"Download {filename}", path.read_bytes(), file_name=filename)


def main_view():
    st.title("RiskNavigator Automation Portal")
    with st.sidebar:
        st.header("Portal")
        st.code("admin / admin123")
        st.caption(f"Last refresh: {st.session_state.refresh_ts}")
        if st.button("Refresh dashboard"):
            st.session_state.refresh_ts = datetime.utcnow().isoformat()
            st.rerun()
        if st.button("Log out"):
            st.session_state.logged_in = False
            st.rerun()

    tabs = st.tabs(["Upload & Auto-Run", "Risk Dashboard", "Reminders", "Downloads"])
    with tabs[0]:
        upload_and_run_view()
    client_name = None
    with tabs[1]:
        client_name = client_selector()
        if client_name:
            risk_dashboard_view(client_name)
    with tabs[2]:
        reminders_view()
    with tabs[3]:
        if client_name is None:
            client_name = st.session_state.selected_client
        if client_name:
            downloads_view(client_name)
        else:
            st.info("Select a client first.")


def main():
    init_state()
    if not st.session_state.logged_in:
        login_view()
    else:
        main_view()


if __name__ == "__main__":
    main()
