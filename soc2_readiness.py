
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Dict, Any, List
import pandas as pd

STATUS_SCORE = {"Yes": 100, "Partial": 50, "No": 0}
SOC2_WEIGHTS = {
    "Control Environment": 0.10,
    "Communication": 0.08,
    "Risk Management": 0.12,
    "Control Activities": 0.12,
    "Logical Access": 0.18,
    "System Operations": 0.15,
    "Change Management": 0.10,
    "Incident Response": 0.10,
    "Availability": 0.03,
    "Confidentiality": 0.02,
}


def normalize_yes_no_partial(value: Any) -> str:
    value = str(value or "").strip()
    if value in STATUS_SCORE:
        return value
    if value.lower() in {"y", "true", "1"}:
        return "Yes"
    if value.lower() in {"n", "false", "0"}:
        return "No"
    return "No"


def normalize_yes_no(value: Any) -> str:
    value = str(value or "").strip()
    if value in {"Yes", "No"}:
        return value
    if value.lower() in {"y", "true", "1"}:
        return "Yes"
    return "No"


def calc_boolean_bonus(row: Dict[str, Any]) -> int:
    bonus = 0
    for field in ["evidence_available", "owner_assigned", "policy_exists", "procedure_exists", "tested_recently"]:
        if normalize_yes_no(row.get(field)) == "Yes":
            bonus += 5
    return min(bonus, 25)


def row_score(row: Dict[str, Any]) -> float | None:
    if normalize_yes_no(row.get("in_scope")) != "Yes":
        return None
    base = STATUS_SCORE[normalize_yes_no_partial(row.get("status"))]
    return min(base + calc_boolean_bonus(row), 100)


def readiness_band(score: float) -> str:
    if score >= 85:
        return "Ready"
    if score >= 70:
        return "Near Ready"
    if score >= 50:
        return "Developing"
    return "Not Ready"


def load_control_intake(file_obj_or_path) -> pd.DataFrame:
    if hasattr(file_obj_or_path, "read"):
        # Uploaded file object
        name = getattr(file_obj_or_path, "name", "").lower()
        if name.endswith(".csv"):
            return pd.read_csv(file_obj_or_path)
        return pd.read_excel(file_obj_or_path, sheet_name="Control Intake")
    path = str(file_obj_or_path)
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path, sheet_name="Control Intake")


def prepare_controls(df: pd.DataFrame) -> pd.DataFrame:
    rename = {c: c.strip() for c in df.columns}
    df = df.rename(columns=rename).copy()

    required = [
        "control_id", "control_area", "control_name", "in_scope", "status",
        "evidence_available", "owner_assigned", "policy_exists", "procedure_exists", "tested_recently"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in ["in_scope", "evidence_available", "owner_assigned", "policy_exists", "procedure_exists", "tested_recently"]:
        df[col] = df[col].apply(normalize_yes_no)
    df["status"] = df["status"].apply(normalize_yes_no_partial)
    df["row_score"] = df.apply(lambda r: row_score(r.to_dict()), axis=1)
    df["priority_hint"] = df["row_score"].apply(lambda x: None if pd.isna(x) else ("High" if x < 50 else "Medium" if x < 70 else "Low"))
    return df


def calculate_soc2_readiness(df: pd.DataFrame) -> Dict[str, Any]:
    in_scope = df[df["in_scope"] == "Yes"].copy()

    if in_scope.empty:
        return {
            "overall_score": 0,
            "readiness_band": "Not Ready",
            "area_scores": {},
            "counts": {"in_scope": 0, "ready": 0, "partial": 0, "missing": 0},
            "top_gaps": [],
            "recommendations": [],
        }

    area_scores = (
        in_scope.groupby("control_area")["row_score"]
        .mean()
        .round(2)
        .to_dict()
    )

    weighted_total = 0.0
    total_weight = 0.0
    for area, score in area_scores.items():
        weight = SOC2_WEIGHTS.get(area, 0.05)
        weighted_total += score * weight
        total_weight += weight
    overall = round(weighted_total / total_weight, 2) if total_weight else 0

    counts = {
        "in_scope": int(len(in_scope)),
        "ready": int((in_scope["row_score"] >= 85).sum()),
        "partial": int(((in_scope["row_score"] >= 50) & (in_scope["row_score"] < 85)).sum()),
        "missing": int((in_scope["row_score"] < 50).sum()),
    }

    top_gaps_df = in_scope.sort_values(["row_score", "control_area", "control_id"]).head(8)
    top_gaps = top_gaps_df[[
        "control_id", "control_area", "control_name", "status", "row_score", "priority_hint"
    ]].to_dict(orient="records")

    recommendations = []
    area_rank = sorted(area_scores.items(), key=lambda x: x[1])[:5]
    for area, score in area_rank:
        action = {
            "area": area,
            "score": score,
            "priority": "High" if score < 50 else "Medium",
            "recommendation": (
                "Close design gaps, assign owners, and collect audit evidence."
                if score < 70 else
                "Finalize testing evidence and prepare audit walkthroughs."
            )
        }
        recommendations.append(action)

    return {
        "overall_score": overall,
        "readiness_band": readiness_band(overall),
        "area_scores": area_scores,
        "counts": counts,
        "top_gaps": top_gaps,
        "recommendations": recommendations,
    }
