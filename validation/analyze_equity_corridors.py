#!/usr/bin/env python3
"""
analyze_equity_corridors.py
===========================
Post-processing script for UrbanEV-v2 (Maryland + DC) simulation output.

Produces three analyses:
  A) Equity dashboard  → equity_analysis.html + equity_metrics.csv
  B) Corridor SoC profiles → corridor_soc_profiles.html + corridor_soc_data.csv
  C) Charger utilization   → charger_utilization.csv  + charger_utilization.html

All spatial data is in EPSG:26985 (NAD83 / Maryland State Plane, metres).

Usage
-----
python analyze_equity_corridors.py \\
    --charging-stats output/ITERS/it.60/60.chargingStats.csv \\
    --scoring        output/scoringComponents.csv \\
    --plans          output/output_plans.xml.gz \\
    --events         output/output_events.xml.gz \\
    --chargers       scenarios/maryland/chargers.xml \\
    --network        scenarios/maryland/network.xml.gz \\
    --corridors      "I-95:l1,l2,l3;I-70:l4,l5,l6" \\
    --output-dir     analysis_results/
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    print("[WARN] plotly not installed — HTML outputs will be skipped.", file=sys.stderr)
    HAS_PLOTLY = False

# ─────────────────────────────────────────────────────────────────────────────
# Constants — consistent with UrbanEVConfigGroup defaults and config.xml
# ─────────────────────────────────────────────────────────────────────────────

# MD electricity rates (USD / kWh)
PRICE_HOME_KWH    = 0.13
PRICE_WORK_KWH    = 0.00   # free at work
PRICE_L1_KWH      = 0.18
PRICE_L2_KWH      = 0.25
PRICE_DCFC_KWH    = 0.48
L2_THRESHOLD_KW   = 3.0
DCFC_THRESHOLD_KW = 50.0

SIM_DAYS          = 7          # QSim endTime = 168 h
WEEKS_PER_MONTH   = 52.18 / 12
SECONDS_PER_DAY   = 86_400
CHARGING_DESERT_M = 30 * 1_609.34   # 30 miles in metres

# MPO income midpoints (USD / yr) for hh_income_detailed 0-9
INCOME_MIDPOINTS = [7_500, 12_500, 20_000, 30_000, 42_500,
                    62_500, 87_500, 125_000, 175_000, 250_000]

# Dwelling-type mapping (MPO_HOME_TYPE codes → label)
DWELLING_MAP = {"1": "SFD", "2": "SFA",
                "3": "MF",  "4": "MF", "5": "MF",
                "0": "Other", "6": "Other"}

RANGE_ANXIETY_DEFAULT = 0.20

# Corridors to analyse when --corridors is not supplied
DEFAULT_CORRIDORS: Dict[str, List[str]] = {
    "I-70":  [],
    "I-68":  [],
    "US-50": [],
    "I-95":  [],
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def open_possibly_gzipped(path: str):
    """Return a text-mode file object, transparently handling .gz."""
    p = Path(path)
    if p.suffix == ".gz":
        return gzip.open(p, "rt", encoding="utf-8")
    return open(p, "r", encoding="utf-8")


def iterparse_xml(path: str):
    """Yield (event, element) from an XML file that may be gzip-compressed."""
    if path.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            for ev, el in ET.iterparse(fh, events=("start", "end")):
                yield ev, el
    else:
        for ev, el in ET.iterparse(path, events=("start", "end")):
            yield ev, el


def haversine_approx(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance in EPSG:26985 (metres)."""
    return math.hypot(x2 - x1, y2 - y1)


# ─────────────────────────────────────────────────────────────────────────────
# A.1  Load charging statistics
# ─────────────────────────────────────────────────────────────────────────────

def load_charging_stats(path: str) -> pd.DataFrame:
    """
    Load the per-session charging CSV (semicolon-delimited).
    Adds derived columns: charger_location ('home'/'work'/'public'),
    charger_power_kw (from chargerId patterns for private chargers),
    unit_price, session_cost.
    """
    print(f"[A] Loading charging stats: {path}")
    df = pd.read_csv(path, sep=";", low_memory=False)
    df.columns = df.columns.str.strip()

    # Normalise vehicleId to string
    df["vehicleId"] = df["vehicleId"].astype(str).str.strip()
    df["chargerId"] = df["chargerId"].astype(str).str.strip()

    # Classify charger location from chargerId naming convention
    # MobsimScopeEventHandling names private chargers as "{personId}_home" / "{personId}_work"
    df["charger_location"] = "public"
    df.loc[df["chargerId"].str.endswith("_home"), "charger_location"] = "home"
    df.loc[df["chargerId"].str.endswith("_work"), "charger_location"] = "work"

    # Unit price per kWh — will be refined once charger power is joined in
    def _price(row):
        if row["charger_location"] == "home":
            return PRICE_HOME_KWH
        if row["charger_location"] == "work":
            return PRICE_WORK_KWH
        return np.nan   # fill after joining charger info

    df["unit_price_kwh"] = df.apply(_price, axis=1)
    df["transmittedEnergy_kWh"] = pd.to_numeric(
        df.get("transmittedEnergy_kWh", 0), errors="coerce").fillna(0)

    # Preliminary session cost (public pricing filled later)
    df["session_cost"] = df["transmittedEnergy_kWh"] * df["unit_price_kwh"].fillna(PRICE_L2_KWH)

    print(f"    {len(df):,} sessions loaded.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# A.2  Load charger infrastructure
# ─────────────────────────────────────────────────────────────────────────────

def load_charger_info(path: str) -> pd.DataFrame:
    """
    Parse chargers.xml → DataFrame with columns:
    chargerId, x, y, chargerType, plugPower_kw, plugCount.
    """
    print(f"[A] Loading charger infrastructure: {path}")
    rows = []
    for ev, el in iterparse_xml(path):
        if ev == "end" and el.tag == "charger":
            rows.append({
                "chargerId":    el.get("id", ""),
                "x":            float(el.get("x", 0)),
                "y":            float(el.get("y", 0)),
                "chargerType":  el.get("type", ""),
                "plugPower_kw": float(el.get("plug_power", 0)) / 1000.0,
                "plugCount":    int(el.get("plug_count", 1)),
            })
            el.clear()

    df = pd.DataFrame(rows)
    print(f"    {len(df):,} chargers loaded.")
    return df


def _public_price(power_kw: float) -> float:
    if power_kw >= DCFC_THRESHOLD_KW:
        return PRICE_DCFC_KWH
    if power_kw >= L2_THRESHOLD_KW:
        return PRICE_L2_KWH
    return PRICE_L1_KWH


def enrich_sessions_with_charger_info(
        sessions: pd.DataFrame, chargers: pd.DataFrame) -> pd.DataFrame:
    """Join charger power and recompute public session costs."""
    merged = sessions.merge(
        chargers[["chargerId", "plugPower_kw", "chargerType", "x", "y"]],
        on="chargerId", how="left")

    # Fill public prices using charger power
    mask_public = merged["charger_location"] == "public"
    merged.loc[mask_public, "unit_price_kwh"] = merged.loc[
        mask_public, "plugPower_kw"].apply(
            lambda p: _public_price(p) if pd.notna(p) else PRICE_L2_KWH)

    merged["session_cost"] = merged["transmittedEnergy_kWh"] * merged["unit_price_kwh"].fillna(0)
    merged["is_dcfc"] = merged["plugPower_kw"].fillna(0) >= DCFC_THRESHOLD_KW
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# A.3  Load person attributes from output_plans.xml.gz
# ─────────────────────────────────────────────────────────────────────────────

def load_person_attributes(path: str) -> pd.DataFrame:
    """
    Stream-parse MATSim plans XML to extract person attributes.
    Returns one row per person with columns: personId + all attribute names.
    """
    print(f"[A] Parsing person attributes from plans: {path}")
    persons = {}
    current_id: Optional[str] = None
    attrs: Dict[str, str] = {}
    inside_attrs = False

    for ev, el in iterparse_xml(path):
        if ev == "start":
            if el.tag == "person":
                current_id = el.get("id")
                attrs = {}
                inside_attrs = False
            elif el.tag == "attributes" and current_id:
                inside_attrs = True
            elif el.tag == "attribute" and inside_attrs and current_id:
                name = el.get("name", "")
                val  = (el.text or "").strip()
                if name:
                    attrs[name] = val
        elif ev == "end":
            if el.tag == "person" and current_id:
                persons[current_id] = {"personId": current_id, **attrs}
                current_id = None
                attrs = {}
                inside_attrs = False
            elif el.tag == "attributes":
                inside_attrs = False
            el.clear()

    df = pd.DataFrame(persons.values())
    print(f"    {len(df):,} persons loaded.")
    return df


def enrich_persons(df: pd.DataFrame) -> pd.DataFrame:
    """Derive income quintile, dwelling category, annual income."""
    df = df.copy()

    # Annual income from bracket index
    def _income(v):
        try:
            idx = int(v)
            return INCOME_MIDPOINTS[idx] if 0 <= idx < len(INCOME_MIDPOINTS) else 62_500
        except (ValueError, TypeError):
            return 62_500

    df["annual_income"] = df.get("hh_income_detailed", pd.Series(dtype=str)).apply(_income)
    df["monthly_income"] = df["annual_income"] / 12

    # Quintiles computed on this population
    df["income_quintile"] = pd.qcut(
        df["annual_income"], q=5,
        labels=["Q1 (<$24K)", "Q2 ($24-43K)", "Q3 ($43-72K)", "Q4 ($72-115K)", "Q5 (>$115K)"],
        duplicates="drop")

    # Dwelling type
    df["dwelling"] = df.get("home_type", pd.Series(dtype=str)).astype(str).map(
        DWELLING_MAP).fillna("Other")

    # Numeric attributes
    for col, default in [("rangeAnxietyThreshold", RANGE_ANXIETY_DEFAULT),
                         ("homeChargerPower", 0.0),
                         ("betaMoney", -6.0)]:
        df[col] = pd.to_numeric(df.get(col, pd.Series(dtype=str)), errors="coerce").fillna(default)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# A.4  Parse events file (streaming) for equity and corridor data
# ─────────────────────────────────────────────────────────────────────────────

def parse_events_for_equity(
        events_path: str,
        corridor_links: Dict[str, Set[str]],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, List[dict]]]:
    """
    Single streaming pass over output_events.xml.gz to extract:
    - soc_events: DataFrame of scoring events (type="scoring") with SoC data
    - fail_events: DataFrame of charging-failed activity-end events
    - corridor_visits: dict[corridor_name → list of {vehicleId, linkId, time, corridor}]

    Returns (soc_df, fail_df, corridor_visits).
    """
    print(f"[A/B] Streaming events: {events_path}")
    all_corridor_links: Set[str] = set()
    for links in corridor_links.values():
        all_corridor_links |= links

    soc_rows: List[dict] = []
    fail_rows: List[dict] = []
    corridor_visits: Dict[str, List[dict]] = defaultdict(list)
    n_events = 0

    for ev, el in iterparse_xml(events_path):
        if ev != "end" or el.tag != "event":
            continue

        n_events += 1
        etype = el.get("type", "")
        t     = float(el.get("time", 0))

        # Custom scoring events from ChargingBehaviourScoring
        if etype == "scoring":
            cost_only = el.get("costOnly", "false").lower() == "true"
            soc = el.get("soc")
            if soc is not None and not cost_only:
                soc_rows.append({
                    "personId":     el.get("person", el.get("personId", "")),
                    "time":         t,
                    "soc":          float(soc),
                    "activityType": el.get("activityType", ""),
                    "startSoc":     float(el.get("startSoc") or 0),
                })

        # Activity-end events: detect charging failures
        elif etype == "actend":
            act_type = el.get("actType", "")
            if "charging failed" in act_type:
                fail_rows.append({
                    "personId": el.get("person", ""),
                    "time":     t,
                    "actType":  act_type,
                    "linkId":   el.get("link", ""),
                })

        # Link-enter events for corridor tracking
        elif etype == "entered link":
            link = el.get("link", "")
            if link in all_corridor_links:
                vid = el.get("vehicle", "")
                for corridor_name, links in corridor_links.items():
                    if link in links:
                        corridor_visits[corridor_name].append({
                            "vehicleId": vid,
                            "linkId":    link,
                            "time":      t,
                        })

        el.clear()
        if n_events % 5_000_000 == 0:
            print(f"    … {n_events:,} events processed")

    print(f"    Done. {n_events:,} events, "
          f"{len(soc_rows):,} SoC records, "
          f"{len(fail_rows):,} failures.")
    return (
        pd.DataFrame(soc_rows),
        pd.DataFrame(fail_rows),
        dict(corridor_visits),
    )


# ─────────────────────────────────────────────────────────────────────────────
# A.5  Compute equity metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_equity_metrics(
        persons: pd.DataFrame,
        sessions: pd.DataFrame,
        soc_events: pd.DataFrame,
        fail_events: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each (income_quintile, dwelling) group compute:
    - monthly_cost_burden    : avg(monthly_cost / monthly_income)
    - failure_rate           : charging failures per agent per simulated week
    - range_anxiety_events   : SoC-below-threshold events per agent per week
    - mean_walking_m         : mean walking distance to charger
    - home_pct / work_pct / public_pct : share of kWh by location
    - mean_cost_per_kwh      : kWh-weighted average price
    - dcfc_pct               : share of kWh from DCFC
    - n_agents               : group size
    """
    print("[A] Computing equity metrics …")

    # ── Per-agent session aggregates ─────────────────────────────────────────
    agg = sessions.groupby("vehicleId").agg(
        total_energy_kwh = ("transmittedEnergy_kWh", "sum"),
        total_cost       = ("session_cost", "sum"),
        home_kwh         = ("transmittedEnergy_kWh",
                            lambda x: x[sessions.loc[x.index, "charger_location"] == "home"].sum()),
        work_kwh         = ("transmittedEnergy_kWh",
                            lambda x: x[sessions.loc[x.index, "charger_location"] == "work"].sum()),
        public_kwh       = ("transmittedEnergy_kWh",
                            lambda x: x[sessions.loc[x.index, "charger_location"] == "public"].sum()),
        dcfc_kwh         = ("transmittedEnergy_kWh",
                            lambda x: x[sessions.loc[x.index, "is_dcfc"] == True].sum()),
        mean_walk_m      = ("walkingDistance", "mean"),
    ).reset_index()

    # Fix: use merge instead of groupby with cross-reference (more robust)
    loc_kwh = sessions.groupby(["vehicleId", "charger_location"])["transmittedEnergy_kWh"].sum().unstack(
        fill_value=0).reset_index()
    for col in ("home", "work", "public"):
        if col not in loc_kwh.columns:
            loc_kwh[col] = 0.0

    dcfc_kwh = sessions[sessions["is_dcfc"]].groupby("vehicleId")[
        "transmittedEnergy_kWh"].sum().reset_index().rename(
        columns={"transmittedEnergy_kWh": "dcfc_kwh"})

    agent_sessions = sessions.groupby("vehicleId").agg(
        total_energy_kwh = ("transmittedEnergy_kWh", "sum"),
        total_cost       = ("session_cost", "sum"),
        mean_walk_m      = ("walkingDistance", "mean"),
    ).reset_index()
    agent_sessions = agent_sessions.merge(loc_kwh[["vehicleId","home","work","public"]],
                                          on="vehicleId", how="left")
    agent_sessions = agent_sessions.merge(dcfc_kwh, on="vehicleId", how="left")
    agent_sessions["dcfc_kwh"] = agent_sessions["dcfc_kwh"].fillna(0)

    # ── Per-agent fail counts ─────────────────────────────────────────────────
    if len(fail_events):
        fail_counts = fail_events.groupby("personId").size().reset_index(
            name="n_failures")
    else:
        fail_counts = pd.DataFrame(columns=["personId", "n_failures"])

    # ── Per-agent SoC-below-threshold counts ─────────────────────────────────
    if len(soc_events):
        # Join person threshold
        soc_w_thresh = soc_events.merge(
            persons[["personId", "rangeAnxietyThreshold"]], on="personId", how="left")
        soc_w_thresh["rangeAnxietyThreshold"] = soc_w_thresh[
            "rangeAnxietyThreshold"].fillna(RANGE_ANXIETY_DEFAULT)
        anxiety_mask = (soc_w_thresh["soc"] > 0) & (
            soc_w_thresh["soc"] < soc_w_thresh["rangeAnxietyThreshold"])
        anxiety_counts = soc_w_thresh[anxiety_mask].groupby("personId").size().reset_index(
            name="n_anxiety_events")
    else:
        anxiety_counts = pd.DataFrame(columns=["personId", "n_anxiety_events"])

    # ── Merge everything onto persons ─────────────────────────────────────────
    p = persons.merge(agent_sessions.rename(columns={"vehicleId": "personId"}),
                      on="personId", how="left")
    p = p.merge(fail_counts, on="personId", how="left")
    p = p.merge(anxiety_counts, on="personId", how="left")

    p["total_energy_kwh"]  = p["total_energy_kwh"].fillna(0)
    p["total_cost"]        = p["total_cost"].fillna(0)
    p["home"]              = p["home"].fillna(0)
    p["work"]              = p["work"].fillna(0)
    p["public"]            = p["public"].fillna(0)
    p["dcfc_kwh"]          = p["dcfc_kwh"].fillna(0)
    p["n_failures"]        = p["n_failures"].fillna(0)
    p["n_anxiety_events"]  = p["n_anxiety_events"].fillna(0)
    p["mean_walk_m"]       = p["mean_walk_m"].fillna(0)

    # Scale simulation week → monthly equivalents
    p["monthly_cost"]     = p["total_cost"] * WEEKS_PER_MONTH / SIM_DAYS * 7
    p["cost_burden"]      = p["monthly_cost"] / p["monthly_income"].clip(lower=1)
    p["failures_per_week"]= p["n_failures"] / (SIM_DAYS / 7)
    p["anxiety_per_week"] = p["n_anxiety_events"] / (SIM_DAYS / 7)
    p["mean_cost_kwh"]    = np.where(p["total_energy_kwh"] > 0,
                                     p["total_cost"] / p["total_energy_kwh"], 0)
    p["home_pct"]         = 100 * p["home"] / p["total_energy_kwh"].clip(lower=1e-9)
    p["work_pct"]         = 100 * p["work"] / p["total_energy_kwh"].clip(lower=1e-9)
    p["public_pct"]       = 100 * p["public"] / p["total_energy_kwh"].clip(lower=1e-9)
    p["dcfc_pct"]         = 100 * p["dcfc_kwh"] / p["total_energy_kwh"].clip(lower=1e-9)

    # ── Group aggregates ──────────────────────────────────────────────────────
    group_cols = ["income_quintile", "dwelling"]
    metrics = p.groupby(group_cols, observed=True).agg(
        n_agents              = ("personId", "count"),
        monthly_cost_burden   = ("cost_burden", "mean"),
        failure_rate          = ("failures_per_week", "mean"),
        range_anxiety_events  = ("anxiety_per_week", "mean"),
        mean_walking_m        = ("mean_walk_m", "mean"),
        home_pct              = ("home_pct", "mean"),
        work_pct              = ("work_pct", "mean"),
        public_pct            = ("public_pct", "mean"),
        mean_cost_per_kwh     = ("mean_cost_kwh", "mean"),
        dcfc_pct              = ("dcfc_pct", "mean"),
    ).reset_index()

    # Keep per-agent df for box plots
    p._equity_agent_df = p   # attach for later use
    print(f"    {len(metrics):,} group combinations computed.")
    return metrics, p   # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# A.6  Build equity HTML dashboard
# ─────────────────────────────────────────────────────────────────────────────

def build_equity_html(metrics: pd.DataFrame, agent_df: pd.DataFrame,
                      output_path: str) -> None:
    if not HAS_PLOTLY:
        print("[A] Skipping HTML (plotly not available).")
        return

    print(f"[A] Building equity dashboard → {output_path}")

    # Pivot for heatmap
    pivot = metrics.pivot_table(
        index="income_quintile", columns="dwelling",
        values="monthly_cost_burden", aggfunc="mean")

    # ── Figure layout: 2×2 grid ───────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Charging Cost Burden (monthly cost / monthly income)",
            "Charging Location Split by Income Quintile (% kWh)",
            "Charging Cost per kWh Distribution by Dwelling Type",
            "DCFC Dependency Rate by Income Quintile (% kWh)",
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.12,
    )

    # 1. Heatmap: income × dwelling → cost burden
    fig.add_trace(go.Heatmap(
        z=pivot.values,
        x=list(pivot.columns),
        y=list(pivot.index),
        colorscale="YlOrRd",
        colorbar=dict(title="Cost burden", x=0.45, len=0.45),
        hovertemplate="Quintile: %{y}<br>Dwelling: %{x}<br>Burden: %{z:.3f}<extra></extra>",
    ), row=1, col=1)

    # 2. Stacked bar: charging location split by income quintile
    quintile_split = metrics.groupby("income_quintile", observed=True)[
        ["home_pct", "work_pct", "public_pct"]].mean().reset_index()
    for col, color, name in [
            ("home_pct",   "#2196F3", "Home"),
            ("work_pct",   "#4CAF50", "Work"),
            ("public_pct", "#FF9800", "Public")]:
        fig.add_trace(go.Bar(
            x=quintile_split["income_quintile"].astype(str),
            y=quintile_split[col],
            name=name, marker_color=color,
            hovertemplate=f"{name}: %{{y:.1f}}%<extra></extra>",
        ), row=1, col=2)
    fig.update_layout(barmode="stack")

    # 3. Box plot: cost per kWh by dwelling type
    for dw in agent_df["dwelling"].dropna().unique():
        sub = agent_df[agent_df["dwelling"] == dw]["mean_cost_kwh"]
        fig.add_trace(go.Box(
            y=sub, name=str(dw),
            boxpoints="outliers",
            hovertemplate=f"Dwelling: {dw}<br>Cost/kWh: %{{y:.3f}}<extra></extra>",
        ), row=2, col=1)

    # 4. Bar: DCFC dependency by income quintile
    dcfc_q = metrics.groupby("income_quintile", observed=True)["dcfc_pct"].mean().reset_index()
    fig.add_trace(go.Bar(
        x=dcfc_q["income_quintile"].astype(str),
        y=dcfc_q["dcfc_pct"],
        marker_color="#9C27B0",
        name="DCFC %",
        hovertemplate="Quintile: %{x}<br>DCFC share: %{y:.1f}%<extra></extra>",
    ), row=2, col=2)

    fig.update_layout(
        title_text="UrbanEV-v2 Maryland+DC — Equity Dashboard",
        height=900,
        showlegend=True,
        paper_bgcolor="#FAFAFA",
        font=dict(family="Arial, sans-serif", size=12),
    )
    fig.update_xaxes(tickangle=-30)

    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"    Saved {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# B  Corridor SoC Profiles
# ─────────────────────────────────────────────────────────────────────────────

def load_network_corridor_links(
        network_path: str, link_ids: Set[str]) -> pd.DataFrame:
    """
    Stream-parse the network XML to extract coordinates of corridor links only.
    Returns DataFrame with columns: linkId, from_x, from_y, to_x, to_y, length.
    """
    print(f"[B] Reading network links for corridors: {network_path}")
    rows = []
    nodes: Dict[str, Tuple[float, float]] = {}

    for ev, el in iterparse_xml(network_path):
        if ev == "end":
            if el.tag == "node":
                nid = el.get("id", "")
                nodes[nid] = (float(el.get("x", 0)), float(el.get("y", 0)))
                el.clear()
            elif el.tag == "link":
                lid = el.get("id", "")
                if lid in link_ids:
                    fn = el.get("from", "")
                    tn = el.get("to", "")
                    fx, fy = nodes.get(fn, (0.0, 0.0))
                    tx, ty = nodes.get(tn, (0.0, 0.0))
                    rows.append({
                        "linkId": lid,
                        "from_x": fx, "from_y": fy,
                        "to_x":   tx, "to_y":   ty,
                        "length": float(el.get("length", 0)),
                    })
                el.clear()

    print(f"    {len(rows)} corridor links found in network.")
    return pd.DataFrame(rows)


def _assign_corridor_distances(
        link_df: pd.DataFrame, link_sequence: List[str]) -> pd.DataFrame:
    """Compute cumulative distance along an ordered link sequence."""
    ordered = link_df.set_index("linkId").reindex(link_sequence).reset_index()
    ordered["cum_dist_m"] = ordered["length"].fillna(0).cumsum() - \
                             ordered["length"].fillna(0)
    return ordered


def compute_corridor_soc(
        corridor_visits: Dict[str, List[dict]],
        soc_events: pd.DataFrame,
        persons: pd.DataFrame,
        sessions: pd.DataFrame,
        link_df: pd.DataFrame,
        corridor_link_sequences: Dict[str, List[str]],
) -> pd.DataFrame:
    """
    For each corridor and vehicle, estimate SoC at each corridor link.

    Strategy:
    - Get the vehicle's SoC scoring events ordered by time.
    - For each corridor traversal, interpolate SoC between the last known
      SoC before entry and the next known SoC after exit.
    - Combine with person attributes (vehicle_type → rangeAnxietyThreshold,
      riskAttitude).

    Returns long DataFrame: corridor, vehicleId, cum_dist_m, estimated_soc,
                             vehicle_type, risk_attitude.
    """
    print("[B] Computing corridor SoC profiles …")
    if soc_events.empty:
        print("    No SoC events — skipping corridor profiles.")
        return pd.DataFrame()

    # Sort SoC events per person
    soc_sorted = soc_events.sort_values(["personId", "time"])
    soc_by_person = {pid: grp for pid, grp in soc_sorted.groupby("personId")}

    # Person attributes for riskAttitude, vehicle type label
    person_attrs = persons.set_index("personId")

    # Link cumulative distances
    link_cum = link_df.set_index("linkId")["length"].fillna(0)

    all_rows = []

    for corridor_name, visits in corridor_visits.items():
        if not visits:
            continue
        link_seq = corridor_link_sequences.get(corridor_name, [])
        link_set = set(link_seq)
        cum_dists: Dict[str, float] = {}
        cumsum = 0.0
        for lid in link_seq:
            cum_dists[lid] = cumsum
            cumsum += link_cum.get(lid, 0.0)

        # Group visits by vehicle
        visits_df = pd.DataFrame(visits)
        for vid, vgroup in visits_df.groupby("vehicleId"):
            pid = str(vid)
            soc_grp = soc_by_person.get(pid, pd.DataFrame())

            if soc_grp.empty:
                continue

            entry_time = vgroup["time"].min()
            exit_time  = vgroup["time"].max()

            # SoC just before entry
            before = soc_grp[soc_grp["time"] <= entry_time]
            after  = soc_grp[soc_grp["time"] >= exit_time]

            soc_entry = before["soc"].iloc[-1] if len(before) else 0.5
            soc_exit  = after["soc"].iloc[0]  if len(after)  else soc_entry

            # Get person metadata
            try:
                pa = person_attrs.loc[pid]
                risk   = str(pa.get("riskAttitude", "moderate"))
                v_type = str(pa.get("vehicle_type", "unknown"))
                thresh = float(pa.get("rangeAnxietyThreshold", RANGE_ANXIETY_DEFAULT))
            except KeyError:
                risk   = "moderate"
                v_type = "unknown"
                thresh = RANGE_ANXIETY_DEFAULT

            # Interpolate SoC for each visited link
            for _, vrow in vgroup.iterrows():
                lid = vrow["linkId"]
                if lid not in cum_dists:
                    continue
                d    = cum_dists[lid]
                frac = d / max(cumsum, 1.0)
                est_soc = soc_entry + (soc_exit - soc_entry) * frac

                all_rows.append({
                    "corridor":    corridor_name,
                    "vehicleId":   vid,
                    "linkId":      lid,
                    "cum_dist_m":  d,
                    "estimated_soc": max(0.0, min(1.0, est_soc)),
                    "vehicle_type": v_type,
                    "risk_attitude": risk,
                    "threshold":   thresh,
                })

    df = pd.DataFrame(all_rows)
    print(f"    {len(df):,} corridor SoC data points.")
    return df


def find_charging_deserts(
        chargers: pd.DataFrame,
        link_df: pd.DataFrame,
        corridor_name: str,
        link_seq: List[str],
        cum_dists: Dict[str, float],
) -> List[Tuple[float, float]]:
    """
    Identify sections > CHARGING_DESERT_M along the corridor with no charger nearby.
    Returns list of (start_m, end_m) gaps.
    """
    if chargers.empty or not link_seq:
        return []

    # Find charger positions along corridor by nearest link
    charger_positions: List[float] = []
    for _, lrow in link_df.iterrows():
        cx, cy = (lrow["from_x"] + lrow["to_x"]) / 2, (lrow["from_y"] + lrow["to_y"]) / 2
        for _, crow in chargers.iterrows():
            d = haversine_approx(cx, cy, crow["x"], crow["y"])
            if d < 5_000:   # within 5km of link midpoint
                pos = cum_dists.get(lrow["linkId"], 0.0)
                charger_positions.append(pos)

    if not charger_positions:
        return [(0.0, cum_dists.get(link_seq[-1], 0.0))] if link_seq else []

    charger_positions = sorted(set(charger_positions))
    total = cum_dists.get(link_seq[-1], 0.0)
    gaps = []
    prev = 0.0
    for pos in charger_positions:
        if pos - prev > CHARGING_DESERT_M:
            gaps.append((prev, pos))
        prev = pos
    if total - prev > CHARGING_DESERT_M:
        gaps.append((prev, total))
    return gaps


def build_corridor_html(
        soc_df: pd.DataFrame,
        chargers: pd.DataFrame,
        corridor_link_sequences: Dict[str, List[str]],
        link_df: pd.DataFrame,
        output_path: str,
) -> None:
    if not HAS_PLOTLY or soc_df.empty:
        print("[B] Skipping corridor HTML (no data or plotly unavailable).")
        return

    print(f"[B] Building corridor dashboard → {output_path}")
    corridors = soc_df["corridor"].unique()
    n_corridors = len(corridors)
    fig = make_subplots(
        rows=n_corridors, cols=1,
        subplot_titles=[f"Corridor: {c}" for c in corridors],
        vertical_spacing=0.08 / max(n_corridors, 1),
    )

    palette = px.colors.qualitative.Plotly
    anxiety_color = "rgba(255,100,100,0.15)"

    for row_idx, corridor in enumerate(corridors, start=1):
        sub = soc_df[soc_df["corridor"] == corridor]
        link_seq = corridor_link_sequences.get(corridor, [])

        # Cumulative distances for this corridor
        cum_dists: Dict[str, float] = {}
        cumsum = 0.0
        for lid in link_seq:
            cum_dists[lid] = cumsum
            if lid in link_df["linkId"].values:
                cumsum += float(link_df.set_index("linkId").loc[lid, "length"])

        # Mean SoC ± std by vehicle type at binned corridor positions
        sub = sub.copy()
        sub["dist_bin_km"] = (sub["cum_dist_m"] / 1000).round(1)
        mean_thresh = sub["threshold"].mean() if len(sub) else RANGE_ANXIETY_DEFAULT

        for vi, vtype in enumerate(sub["vehicle_type"].unique()):
            vsub = sub[sub["vehicle_type"] == vtype]
            binned = vsub.groupby("dist_bin_km")["estimated_soc"].agg(["mean","std"]).reset_index()
            binned["std"] = binned["std"].fillna(0)
            color = palette[vi % len(palette)]

            # Mean line
            fig.add_trace(go.Scatter(
                x=binned["dist_bin_km"], y=binned["mean"],
                mode="lines", name=vtype,
                line=dict(color=color),
                legendgroup=vtype,
                showlegend=(row_idx == 1),
                hovertemplate=f"{vtype}<br>km: %{{x}}<br>SoC: %{{y:.2f}}<extra></extra>",
            ), row=row_idx, col=1)

            # ±1 std band
            x_band = list(binned["dist_bin_km"]) + list(binned["dist_bin_km"])[::-1]
            y_band = (list(binned["mean"] + binned["std"]) +
                      list((binned["mean"] - binned["std"]).clip(lower=0))[::-1])
            fig.add_trace(go.Scatter(
                x=x_band, y=y_band,
                fill="toself", fillcolor=color.replace("rgb", "rgba").replace(")", ",0.15)"),
                line=dict(width=0), showlegend=False,
                hoverinfo="skip",
            ), row=row_idx, col=1)

        # Anxiety threshold horizontal line
        fig.add_hline(y=mean_thresh, line_dash="dot", line_color="red",
                      annotation_text="Range anxiety threshold",
                      row=row_idx, col=1)

        # Charging desert zones
        deserts = find_charging_deserts(chargers, link_df, corridor, link_seq, cum_dists)
        for (d_start, d_end) in deserts:
            fig.add_vrect(
                x0=d_start / 1000, x1=d_end / 1000,
                fillcolor="orange", opacity=0.15,
                annotation_text="Charging desert",
                annotation_position="top left",
                row=row_idx, col=1)

    fig.update_yaxes(title_text="SoC (0–1)", range=[0, 1.05])
    fig.update_xaxes(title_text="Distance from corridor start (km)")
    fig.update_layout(
        title_text="UrbanEV-v2 — Corridor SoC Profiles",
        height=400 * max(n_corridors, 1),
        paper_bgcolor="#FAFAFA",
        font=dict(family="Arial, sans-serif", size=12),
    )
    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"    Saved {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# C  Charger Utilization
# ─────────────────────────────────────────────────────────────────────────────

def compute_charger_utilization(
        sessions: pd.DataFrame, chargers: pd.DataFrame) -> pd.DataFrame:
    """
    For each charger compute utilization metrics over the simulated period.
    """
    print("[C] Computing charger utilization …")

    if sessions.empty:
        return pd.DataFrame()

    # MATSim times are in seconds from midnight of day 1
    sess = sessions.copy()
    sess["start_s"] = pd.to_numeric(sess.get("startTime_matsim", sess.get("startTime", 0)),
                                    errors="coerce").fillna(0)
    sess["end_s"]   = pd.to_numeric(sess.get("endTime_matsim",   sess.get("endTime",   0)),
                                    errors="coerce").fillna(0)
    sess["dur_s"]   = (sess["end_s"] - sess["start_s"]).clip(lower=0)

    # Peak hours: 18:00–20:00 each day (in seconds of day)
    def in_peak(row):
        start_of_day = row["start_s"] % SECONDS_PER_DAY
        end_of_day   = row["end_s"]   % SECONDS_PER_DAY
        return (start_of_day < 72_000) and (end_of_day > 64_800)  # 18–20h

    sess["is_peak"] = sess.apply(in_peak, axis=1)

    total_sim_s = SIM_DAYS * SECONDS_PER_DAY

    rows = []
    charger_meta = chargers.set_index("chargerId")

    for cid, grp in sess.groupby("chargerId"):
        n_sessions    = len(grp)
        mean_dur_s    = grp["dur_s"].mean()
        mean_energy   = grp["transmittedEnergy_kWh"].mean()
        total_energy  = grp["transmittedEnergy_kWh"].sum()
        peak_sessions = grp["is_peak"].sum()

        # Utilisation: fraction of simulation time at least one plug in use
        # Approximate via union of session intervals
        plug_count = 1
        pwr_kw     = np.nan
        try:
            meta       = charger_meta.loc[cid]
            plug_count = int(meta["plugCount"])
            pwr_kw     = float(meta["plugPower_kw"])
        except KeyError:
            pass

        # Sort sessions and compute occupied-time union
        intervals = sorted(zip(grp["start_s"].tolist(), grp["end_s"].tolist()))
        occupied_s  = 0.0
        queue_events = 0
        current_end  = -1.0
        simultaneous = 0
        for s, e in intervals:
            if s < current_end:
                simultaneous += 1
                if simultaneous >= plug_count:
                    queue_events += 1
            else:
                simultaneous = 1
                occupied_s += max(0.0, e - max(s, current_end if current_end > s else s))
                current_end = e
            current_end = max(current_end, e)

        utilisation_pct = 100.0 * min(occupied_s / max(total_sim_s, 1), 1.0)
        peak_util       = 100.0 * peak_sessions / max(n_sessions, 1)

        # Revenue
        price = _public_price(pwr_kw) if pd.notna(pwr_kw) else PRICE_L2_KWH
        if cid.endswith("_home"):
            price = PRICE_HOME_KWH
        elif cid.endswith("_work"):
            price = PRICE_WORK_KWH
        revenue = total_energy * price

        # Charger coordinates
        x, y = (charger_meta.loc[cid, "x"] if cid in charger_meta.index else np.nan,
                 charger_meta.loc[cid, "y"] if cid in charger_meta.index else np.nan)

        rows.append({
            "chargerId":           cid,
            "x":                   x,
            "y":                   y,
            "plugPower_kw":        pwr_kw,
            "plugCount":           plug_count,
            "n_sessions":          n_sessions,
            "utilisation_pct":     round(utilisation_pct, 2),
            "peak_util_pct":       round(peak_util, 2),
            "queue_events":        queue_events,
            "mean_duration_min":   round(mean_dur_s / 60, 1),
            "mean_energy_kwh":     round(mean_energy, 3),
            "total_energy_kwh":    round(total_energy, 2),
            "revenue_usd":         round(revenue, 2),
        })

    df = pd.DataFrame(rows).sort_values("utilisation_pct", ascending=False)
    print(f"    {len(df):,} chargers with sessions.")
    return df


def build_utilization_html(util_df: pd.DataFrame, output_path: str) -> None:
    if not HAS_PLOTLY or util_df.empty:
        print("[C] Skipping utilization HTML.")
        return

    print(f"[C] Building utilization dashboard → {output_path}")

    public_only = util_df[~util_df["chargerId"].str.endswith(("_home", "_work"), na=False)]

    top10_over  = public_only.nlargest(10, "utilisation_pct")
    top10_under = public_only.nsmallest(10, "utilisation_pct")

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Top-10 Overloaded Chargers (% time occupied)",
            "Top-10 Underutilised Chargers (% time occupied)",
            "Utilisation Distribution by Charger Type",
            "Spatial: Utilisation (circle area ∝ sessions)",
        ],
        vertical_spacing=0.18,
    )

    bar_kwargs = dict(marker_color="#E53935", row=1, col=1)
    fig.add_trace(go.Bar(
        x=top10_over["chargerId"].astype(str).str[-16:],
        y=top10_over["utilisation_pct"],
        name="Overloaded",
        hovertemplate="%{x}<br>Util: %{y:.1f}%<extra></extra>",
        **bar_kwargs), **{k: v for k, v in bar_kwargs.items() if k in ("row", "col")})
    fig.update_traces(marker_color="#E53935", selector=dict(name="Overloaded"))

    fig.add_trace(go.Bar(
        x=top10_under["chargerId"].astype(str).str[-16:],
        y=top10_under["utilisation_pct"],
        name="Underutilised", marker_color="#43A047",
        hovertemplate="%{x}<br>Util: %{y:.1f}%<extra></extra>",
    ), row=1, col=2)

    fig.add_trace(go.Box(
        y=public_only[public_only["plugPower_kw"].fillna(0) >= DCFC_THRESHOLD_KW]["utilisation_pct"],
        name="DCFC", boxpoints="outliers", marker_color="#7B1FA2",
    ), row=2, col=1)
    fig.add_trace(go.Box(
        y=public_only[public_only["plugPower_kw"].fillna(0) < DCFC_THRESHOLD_KW]["utilisation_pct"],
        name="L2/L1", boxpoints="outliers", marker_color="#0288D1",
    ), row=2, col=1)

    # Spatial scatter (if coords available)
    has_coords = public_only[["x","y"]].notna().all(axis=1)
    if has_coords.any():
        sp = public_only[has_coords]
        fig.add_trace(go.Scatter(
            x=sp["x"], y=sp["y"],
            mode="markers",
            marker=dict(
                size=(sp["n_sessions"] / sp["n_sessions"].max() * 30).clip(lower=4),
                color=sp["utilisation_pct"],
                colorscale="YlOrRd",
                showscale=True,
                colorbar=dict(title="Util %", x=1.02),
            ),
            text=sp["chargerId"].astype(str),
            hovertemplate="%{text}<br>x=%{x:.0f} y=%{y:.0f}<br>Util: %{marker.color:.1f}%<extra></extra>",
            name="Chargers",
        ), row=2, col=2)

    fig.update_layout(
        title_text="UrbanEV-v2 Maryland+DC — Charger Utilization Report",
        height=850,
        showlegend=True,
        paper_bgcolor="#FAFAFA",
        font=dict(family="Arial, sans-serif", size=12),
    )
    fig.update_xaxes(tickangle=-35)
    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"    Saved {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_corridors(spec: Optional[str]) -> Dict[str, List[str]]:
    """
    Parse corridor spec string: "I-95:l1,l2,l3;I-70:l4,l5"
    Returns dict[corridor_name → [linkId, ...]].
    """
    if not spec:
        return {k: [] for k in DEFAULT_CORRIDORS}
    corridors: Dict[str, List[str]] = {}
    for part in spec.split(";"):
        part = part.strip()
        if ":" in part:
            name, links = part.split(":", 1)
            corridors[name.strip()] = [l.strip() for l in links.split(",") if l.strip()]
        elif part:
            corridors[part] = []
    return corridors


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="UrbanEV-v2 equity & corridor post-processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--charging-stats", required=True,
                   help="Path to {iter}.chargingStats.csv (semicolon-delimited)")
    p.add_argument("--scoring",        default=None,
                   help="Path to scoringComponents.csv (optional)")
    p.add_argument("--plans",          required=True,
                   help="Path to output_plans.xml or output_plans.xml.gz")
    p.add_argument("--events",         required=True,
                   help="Path to output_events.xml or output_events.xml.gz")
    p.add_argument("--chargers",       required=True,
                   help="Path to chargers.xml")
    p.add_argument("--network",        default=None,
                   help="Path to network XML (needed for corridor analysis)")
    p.add_argument("--corridors",      default=None,
                   help='Corridor link spec: "I-95:l1,l2;I-70:l3,l4" '
                        '(if omitted, placeholder corridors are used)')
    p.add_argument("--output-dir",     default="analysis_results",
                   help="Directory for all output files (created if needed)")
    p.add_argument("--skip-events",    action="store_true",
                   help="Skip expensive events-file parsing (equity scoring metrics "
                        "and corridor visits will be unavailable)")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  UrbanEV-v2 Post-processing  →  {out_dir}/")
    print(f"{'='*60}\n")

    # ── Load shared data ──────────────────────────────────────────────────────
    chargers = load_charger_info(args.chargers)
    sessions_raw = load_charging_stats(args.charging_stats)
    sessions = enrich_sessions_with_charger_info(sessions_raw, chargers)

    persons_raw = load_person_attributes(args.plans)
    persons = enrich_persons(persons_raw)

    corridors = parse_corridors(args.corridors)
    corridor_link_sets = {k: set(v) for k, v in corridors.items()}

    # ── Parse events (single pass covers A and B) ─────────────────────────────
    if args.skip_events:
        print("[SKIP] Events parsing skipped (--skip-events).")
        soc_events  = pd.DataFrame()
        fail_events = pd.DataFrame()
        corridor_visits: Dict[str, List[dict]] = {}
    else:
        soc_events, fail_events, corridor_visits = parse_events_for_equity(
            args.events, corridor_link_sets)

    # ── A) Equity analysis ────────────────────────────────────────────────────
    print("\n--- Analysis A: Equity Metrics ---")
    eq_metrics, agent_df = compute_equity_metrics(
        persons, sessions, soc_events, fail_events)

    eq_csv = out_dir / "equity_metrics.csv"
    eq_metrics.to_csv(eq_csv, index=False)
    print(f"[A] Saved {eq_csv}")

    build_equity_html(
        eq_metrics, agent_df,
        str(out_dir / "equity_analysis.html"))

    # ── B) Corridor SoC profiles ──────────────────────────────────────────────
    print("\n--- Analysis B: Corridor SoC Profiles ---")
    has_corridor_links = any(bool(v) for v in corridors.values())

    if not has_corridor_links:
        print("[B] No corridor links specified — corridor analysis skipped.")
        print("    Provide link IDs with --corridors to enable this analysis.")
        corridor_soc = pd.DataFrame()
        link_df = pd.DataFrame()
    else:
        all_link_ids: Set[str] = set()
        for lids in corridors.values():
            all_link_ids |= set(lids)

        if args.network:
            link_df = load_network_corridor_links(args.network, all_link_ids)
        else:
            print("[B] --network not supplied; using zero-length link geometry.")
            link_df = pd.DataFrame(
                {"linkId": list(all_link_ids), "from_x": 0, "from_y": 0,
                 "to_x": 0, "to_y": 0, "length": 0})

        corridor_soc = compute_corridor_soc(
            corridor_visits, soc_events, persons, sessions,
            link_df, corridors)

        if not corridor_soc.empty:
            soc_csv = out_dir / "corridor_soc_data.csv"
            corridor_soc.to_csv(soc_csv, index=False)
            print(f"[B] Saved {soc_csv}")

        build_corridor_html(
            corridor_soc, chargers, corridors, link_df,
            str(out_dir / "corridor_soc_profiles.html"))

    # ── C) Charger utilization ────────────────────────────────────────────────
    print("\n--- Analysis C: Charger Utilization ---")
    util_df = compute_charger_utilization(sessions, chargers)

    if not util_df.empty:
        util_csv = out_dir / "charger_utilization.csv"
        util_df.to_csv(util_csv, index=False)
        print(f"[C] Saved {util_csv}")

        # Summary
        pub = util_df[~util_df["chargerId"].str.endswith(("_home", "_work"), na=False)]
        if len(pub):
            print(f"    Public chargers: {len(pub)}, "
                  f"mean util {pub['utilisation_pct'].mean():.1f}%, "
                  f"total queue events {pub['queue_events'].sum():,}")
            print(f"    Top overloaded:  {pub.nlargest(1,'utilisation_pct')['chargerId'].values}")
            print(f"    Least used:      {pub.nsmallest(1,'utilisation_pct')['chargerId'].values}")

        build_utilization_html(util_df, str(out_dir / "charger_utilization.html"))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  DONE")
    print(f"  Output directory: {out_dir.resolve()}")
    outputs = list(out_dir.glob("*.csv")) + list(out_dir.glob("*.html"))
    for f in sorted(outputs):
        size_kb = f.stat().st_size / 1024
        print(f"    {f.name:<45} {size_kb:>8.1f} kB")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
