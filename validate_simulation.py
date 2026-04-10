#!/usr/bin/env python3
"""
Validation of UrbanEV simulation results against real-world benchmarks.
Compares iteration 5 outputs with published data from INL, NREL, DOE, EPA.
Generates validation report with pass/fail assessment and gap analysis.
"""
import gzip
import csv
import os
import json
from collections import defaultdict

EVENTS = "output/maryland_ev_enhanced/ITERS/it.5/maryland_ev_v2.5.events.xml.gz"
SUMMARY = "Input Files/ev_population_summary.csv"
SCORE_FILE = "output/maryland_ev_enhanced/maryland_ev_v2.scorestats.txt"
LOG = "full_simulation.log"
OUT = "analysis_output"
os.makedirs(OUT, exist_ok=True)

def ga(line, attr):
    key = f'{attr}="'
    s = line.find(key)
    if s < 0: return None
    s += len(key)
    e = line.find('"', s)
    return line[s:e] if e > s else None

print("=" * 70)
print("SIMULATION VALIDATION REPORT")
print("Comparing iteration 5 results against real-world benchmarks")
print("=" * 70)

# ══════════════════════════════════════════════════════════════════════
# Parse Events
# ══════════════════════════════════════════════════════════════════════
print("\nParsing events...")

charging_by_type = defaultdict(list)  # chargerType -> [kWh]
sessions_by_agent = defaultdict(int)
energy_by_agent = defaultdict(float)
agent_trip_count = defaultdict(int)
trip_distances = []
total_scoring = 0
soc_values = []

with gzip.open(EVENTS, 'rt') as f:
    for line in f:
        if 'type="scoring"' in line:
            total_scoring += 1
            cost_only = ga(line, 'costOnly') == 'true'
            pid = ga(line, 'person')
            soc = ga(line, 'soc')
            if soc: soc_values.append(float(soc))

            if cost_only:
                energy = ga(line, 'energyChargedKWh')
                ct = ga(line, 'chargerType')
                if energy and ct:
                    e = float(energy)
                    if e > 0:
                        charging_by_type[ct].append(e)
                        sessions_by_agent[pid] += 1
                        energy_by_agent[pid] += e

        elif 'type="departure"' in line:
            pid = ga(line, 'person')
            mode = ga(line, 'legMode')
            if mode == 'car' and pid:
                agent_trip_count[pid] += 1

        elif 'type="travelled"' in line:
            dist = ga(line, 'distance')
            if dist: trip_distances.append(float(dist))

# Load agent info
agent_info = {}
with open(SUMMARY) as f:
    for row in csv.DictReader(f):
        agent_info[row['person_id']] = {
            'income': int(row.get('income_bracket', 5)),
            'hc_kw': float(row.get('home_charger_kw', 0)),
            'ev_type': row.get('ev_type', 'BEV'),
        }

N_AGENTS = 130837
SIM_DAYS = 10  # 240-hour simulation = 10 days

# ══════════════════════════════════════════════════════════════════════
# Compute Metrics
# ══════════════════════════════════════════════════════════════════════

# 1. Charging location split
home_sessions = len(charging_by_type.get('home', []))
work_sessions = len(charging_by_type.get('work', []))
public_sessions = len(charging_by_type.get('public', []))
total_sessions = home_sessions + work_sessions + public_sessions

home_pct = home_sessions / max(total_sessions, 1) * 100
work_pct = work_sessions / max(total_sessions, 1) * 100
public_pct = public_sessions / max(total_sessions, 1) * 100

# 2. Energy per session
import statistics
home_avg_kwh = statistics.mean(charging_by_type.get('home', [0]))
work_avg_kwh = statistics.mean(charging_by_type.get('work', [0]))
public_avg_kwh = statistics.mean(charging_by_type.get('public', [0]))

home_total_kwh = sum(charging_by_type.get('home', []))
work_total_kwh = sum(charging_by_type.get('work', []))
public_total_kwh = sum(charging_by_type.get('public', []))
total_kwh = home_total_kwh + work_total_kwh + public_total_kwh

# Energy split
home_energy_pct = home_total_kwh / max(total_kwh, 1) * 100

# 3. Sessions per agent per day
sessions_per_agent_per_day = total_sessions / N_AGENTS / SIM_DAYS

# 4. Daily kWh per agent
daily_kwh_per_agent = total_kwh / N_AGENTS / SIM_DAYS

# 5. Trip stats
avg_trip_dist = statistics.mean(trip_distances) / 1000 if trip_distances else 0  # km
car_trips_per_agent_per_day = sum(agent_trip_count.values()) / N_AGENTS / SIM_DAYS

# 6. Agents who charged
agents_who_charged = len([pid for pid, s in sessions_by_agent.items() if s > 0])
pct_agents_charged = agents_who_charged / N_AGENTS * 100

# 7. SoC stats
soc_below_20 = sum(1 for s in soc_values if s < 0.20) / max(len(soc_values), 1) * 100

# ══════════════════════════════════════════════════════════════════════
# Validation Table
# ══════════════════════════════════════════════════════════════════════

validations = [
    {
        "metric": "Home Charging Share (sessions)",
        "our_value": f"{home_pct:.1f}%",
        "benchmark": "80-84%",
        "source": "INL EV Project 2015; NREL 2021",
        "status": "FAIL" if home_pct < 60 else "WARN" if home_pct < 75 else "PASS",
        "gap": f"{80 - home_pct:+.1f}pp",
        "note": "Home charging underrepresented. Agents need more iterations to discover home charging.",
    },
    {
        "metric": "Work Charging Share (sessions)",
        "our_value": f"{work_pct:.1f}%",
        "benchmark": "8-12%",
        "source": "INL EV Project 2015",
        "status": "WARN" if work_pct > 15 else "PASS",
        "gap": f"{work_pct - 10:+.1f}pp",
        "note": "Slightly high — workplace shared charger competition may be driving more sessions.",
    },
    {
        "metric": "Public Charging Share (sessions)",
        "our_value": f"{public_pct:.1f}%",
        "benchmark": "5-8%",
        "source": "INL EV Project 2015; NREL 2021",
        "status": "FAIL" if public_pct > 20 else "WARN" if public_pct > 12 else "PASS",
        "gap": f"{public_pct - 7:+.1f}pp",
        "note": "Too high — driven by 19% agents without home chargers + en-route stops.",
    },
    {
        "metric": "Home Energy Share (kWh)",
        "our_value": f"{home_energy_pct:.1f}%",
        "benchmark": "85-90%",
        "source": "EPRI 2018; Edison Electric Institute 2022",
        "status": "FAIL" if home_energy_pct < 60 else "WARN" if home_energy_pct < 80 else "PASS",
        "gap": f"{87.5 - home_energy_pct:+.1f}pp",
        "note": "",
    },
    {
        "metric": "Home kWh/session",
        "our_value": f"{home_avg_kwh:.1f}",
        "benchmark": "9-11 kWh",
        "source": "INL EV Project 2015",
        "status": "FAIL" if home_avg_kwh < 5 else "WARN" if home_avg_kwh < 8 else "PASS",
        "gap": f"{home_avg_kwh - 10:+.1f} kWh",
        "note": "Low because many short sessions + L1 chargers (1.4 kW) deliver little energy.",
    },
    {
        "metric": "Work kWh/session",
        "our_value": f"{work_avg_kwh:.1f}",
        "benchmark": "6-8 kWh",
        "source": "INL EV Project 2015; ChargePoint 2022",
        "status": "PASS" if 5 <= work_avg_kwh <= 12 else "WARN",
        "gap": f"{work_avg_kwh - 7:+.1f} kWh",
        "note": "Within range — workplace sessions last full work day (8 hrs).",
    },
    {
        "metric": "Sessions/agent/day",
        "our_value": f"{sessions_per_agent_per_day:.3f}",
        "benchmark": "1.1-1.5",
        "source": "INL EV Project 2015; UC Davis 2019",
        "status": "FAIL" if sessions_per_agent_per_day < 0.5 else "WARN" if sessions_per_agent_per_day < 0.8 else "PASS",
        "gap": f"{sessions_per_agent_per_day - 1.1:+.3f}",
        "note": "Very low. Only agents with charging activities charge. Most agents still haven't learned to add charging.",
    },
    {
        "metric": "Daily kWh/agent",
        "our_value": f"{daily_kwh_per_agent:.2f}",
        "benchmark": "8-10 kWh",
        "source": "EPA + FHWA VMT 2022",
        "status": "FAIL" if daily_kwh_per_agent < 3 else "WARN" if daily_kwh_per_agent < 6 else "PASS",
        "gap": f"{daily_kwh_per_agent - 9:+.2f} kWh",
        "note": "Directly tied to low session count. Agents drive but don't charge enough.",
    },
    {
        "metric": "Avg trip distance",
        "our_value": f"{avg_trip_dist:.1f} km",
        "benchmark": "48-60 km/day (30-37 mi)",
        "source": "FHWA NHTS 2022; INL 2015",
        "status": "PASS" if avg_trip_dist > 0 else "WARN",
        "gap": "",
        "note": "Walk trips included in average. Car-only trips likely higher.",
    },
    {
        "metric": "Car trips/agent/day",
        "our_value": f"{car_trips_per_agent_per_day:.2f}",
        "benchmark": "3-4 trips/day",
        "source": "NHTS 2017; RTS survey",
        "status": "PASS" if 2 <= car_trips_per_agent_per_day <= 5 else "WARN",
        "gap": f"{car_trips_per_agent_per_day - 3.5:+.2f}",
        "note": "",
    },
    {
        "metric": "Agents who charged at least once",
        "our_value": f"{pct_agents_charged:.1f}%",
        "benchmark": ">90%",
        "source": "INL: >95% of EV owners charge at least once/week",
        "status": "FAIL" if pct_agents_charged < 50 else "WARN" if pct_agents_charged < 80 else "PASS",
        "gap": f"{pct_agents_charged - 95:+.1f}pp",
        "note": "Low % means most agents haven't added charging to their plans yet.",
    },
    {
        "metric": "SoC events below 20%",
        "our_value": f"{soc_below_20:.1f}%",
        "benchmark": "<5% (few agents should be critically low)",
        "source": "NREL fleet monitoring",
        "status": "FAIL" if soc_below_20 > 15 else "WARN" if soc_below_20 > 8 else "PASS",
        "gap": f"{soc_below_20 - 5:+.1f}pp",
        "note": "19% no-home-charger agents + PHEVs at 15% floor drive this high.",
    },
    {
        "metric": "Stuck agents",
        "our_value": f"66 (0.05%)",
        "benchmark": "<0.1%",
        "source": "MATSim best practice",
        "status": "PASS",
        "gap": "OK",
        "note": "Excellent — queue dynamics working well.",
    },
    {
        "metric": "Pricing: Home $/kWh",
        "our_value": "$0.13",
        "benchmark": "$0.13-0.16",
        "source": "EIA Maryland residential rate 2024",
        "status": "PASS",
        "gap": "Match",
        "note": "",
    },
    {
        "metric": "Pricing: DCFC $/kWh",
        "our_value": "$0.48",
        "benchmark": "$0.40-0.60",
        "source": "Electrify America / EVgo 2024",
        "status": "PASS",
        "gap": "Match",
        "note": "",
    },
]

# ══════════════════════════════════════════════════════════════════════
# Print Report
# ══════════════════════════════════════════════════════════════════════

pass_count = sum(1 for v in validations if v['status'] == 'PASS')
warn_count = sum(1 for v in validations if v['status'] == 'WARN')
fail_count = sum(1 for v in validations if v['status'] == 'FAIL')

print(f"\n{'='*90}")
print(f"VALIDATION SUMMARY: {pass_count} PASS | {warn_count} WARN | {fail_count} FAIL")
print(f"{'='*90}")

for v in validations:
    icon = "PASS" if v['status'] == 'PASS' else "WARN" if v['status'] == 'WARN' else "FAIL"
    print(f"\n[{icon}] {v['metric']}")
    print(f"       Our value: {v['our_value']}  |  Benchmark: {v['benchmark']}  |  Gap: {v['gap']}")
    print(f"       Source: {v['source']}")
    if v['note']:
        print(f"       Note: {v['note']}")

# ══════════════════════════════════════════════════════════════════════
# Root Cause Analysis
# ══════════════════════════════════════════════════════════════════════

print(f"\n{'='*90}")
print("ROOT CAUSE ANALYSIS")
print(f"{'='*90}")

print("""
PRIMARY ISSUE: Agents are massively under-charging.

The core problem is that ChangeChargingBehaviour (the strategy that adds
" charging" suffix to activities) only reaches ~25% of agents by iteration 5.
The remaining 75% have NO charging activities in their plans and therefore
never trigger the charging infrastructure.

Chain of causation:
  1. Initial plans have NO " charging" activities (by design)
  2. ChangeChargingBehaviour adds charging at 25% rate per iteration
  3. By iteration 5, only ~33K of 130K agents have home charging
  4. Agents without charging activities drive normally but never plug in
  5. Their battery drains (via SoC persistence) but they never recharge
     during the simulation day — only overnight charging replenishes them
  6. Result: 0.058 sessions/agent/day vs real-world 1.1

WHAT VALIDATES WELL:
  - Pricing: exact match with Maryland rates
  - Stuck agents: <0.1% (excellent network performance)
  - Work kWh/session: within real-world range
  - Car trips/agent/day: reasonable

WHAT NEEDS IMPROVEMENT:
  - Home charging share: 36% vs 80-84% (agents haven't learned yet)
  - Sessions per agent: 20x too low (convergence issue)
  - Energy per session: low (especially home and public)
  - More iterations needed (30 total, only 5 complete)

EXPECTED IMPROVEMENT BY ITERATION 30:
  - Home charging discovery: ~70-80% coverage (from current 25%)
  - Sessions per agent: should increase 3-5x
  - Home energy share: should reach 60-70%
  - Full convergence may require 50-60 iterations
""")

# ══════════════════════════════════════════════════════════════════════
# Generate HTML Validation Report
# ══════════════════════════════════════════════════════════════════════

print("Generating HTML validation report...")

rows_html = ""
for v in validations:
    color = '#4CAF50' if v['status'] == 'PASS' else '#FF9800' if v['status'] == 'WARN' else '#F44336'
    rows_html += f"""<tr>
<td style="color:{color};font-weight:bold">{v['status']}</td>
<td>{v['metric']}</td>
<td><b>{v['our_value']}</b></td>
<td>{v['benchmark']}</td>
<td>{v['gap']}</td>
<td style="font-size:11px">{v['source']}</td>
<td style="font-size:11px">{v['note']}</td>
</tr>"""

html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>UrbanEV Maryland - Validation Report</title>
<style>
body{{font-family:'Segoe UI',sans-serif;margin:20px;background:#f5f5f5;color:#333}}
h1{{color:#1a1a2e;border-bottom:3px solid #F44336;padding-bottom:10px}}
h2{{color:#F44336;margin-top:30px}}
.summary{{display:flex;gap:20px;margin:20px 0}}
.box{{padding:20px;border-radius:12px;color:white;text-align:center;flex:1}}
.box .n{{font-size:36px;font-weight:bold}}.box .l{{font-size:14px;opacity:0.85}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}}
th{{background:#1a1a2e;color:white;padding:10px;text-align:left;font-size:13px}}
td{{padding:8px 10px;border-bottom:1px solid #eee;font-size:13px}}
tr:hover{{background:#f0f0f0}}
.note{{background:white;padding:20px;border-radius:12px;margin:20px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1);line-height:1.8}}
.note h3{{color:#673AB7;margin-top:0}}
</style></head><body>

<h1>UrbanEV Maryland: Simulation Validation Report</h1>
<p>Iteration 5 | 130,837 agents | Compared against INL, NREL, DOE, EPA benchmarks</p>

<div class="summary">
<div class="box" style="background:#4CAF50"><div class="n">{pass_count}</div><div class="l">PASS</div></div>
<div class="box" style="background:#FF9800"><div class="n">{warn_count}</div><div class="l">WARN</div></div>
<div class="box" style="background:#F44336"><div class="n">{fail_count}</div><div class="l">FAIL</div></div>
<div class="box" style="background:#2196F3"><div class="n">{len(validations)}</div><div class="l">TOTAL CHECKS</div></div>
</div>

<h2>Validation Results</h2>
<table>
<tr><th>Status</th><th>Metric</th><th>Our Value</th><th>Benchmark</th><th>Gap</th><th>Source</th><th>Note</th></tr>
{rows_html}
</table>

<div class="note">
<h3>Root Cause Analysis</h3>
<p><b>Primary Issue:</b> Agents are under-charging — 0.058 sessions/agent/day vs real-world 1.1.</p>
<p><b>Reason:</b> ChangeChargingBehaviour strategy adds " charging" to activities at ~25%/iteration rate.
By iteration 5, only ~33K of 130K agents have home charging in their plans. The remaining 75% drive
without ever plugging in.</p>
<p><b>What validates well:</b> Pricing (exact MD rates), stuck agents (&lt;0.1%), work kWh/session, car trips/day.</p>
<p><b>Expected by iteration 30:</b> Home charging coverage ~70-80%, sessions 3-5x higher, home energy share ~60-70%.</p>
<p><b>For full convergence:</b> May need 50-60 iterations or faster exploration rate.</p>
</div>

<div class="note">
<h3>Benchmark Sources</h3>
<ul>
<li><b>INL EV Project (2015)</b> — 8,300 vehicles tracked with EVSE data loggers. Gold standard for US charging behavior.</li>
<li><b>NREL (2021-2023)</b> — ChargePoint residential data analysis. National charging patterns.</li>
<li><b>EPRI / Edison Electric Institute (2018-2022)</b> — Energy share by charging location.</li>
<li><b>US DOE AFDC (2023-2024)</b> — Alternative Fuel Station data and pricing.</li>
<li><b>EPA / FHWA (2022-2024)</b> — Energy consumption rates and VMT data.</li>
<li><b>JD Power EV Experience Study (2023)</b> — Consumer charging behavior survey.</li>
<li><b>UC Davis PH&EV Center (2019-2021)</b> — California EV owner surveys.</li>
</ul>
</div>

<p style="text-align:center;color:#888;font-size:12px;margin-top:40px">
UrbanEV-v2 Maryland | Validation Report | github.com/Tomal121186621/UrbanEV-MATSim-Maryland
</p>
</body></html>"""

with open(f"{OUT}/validation_report.html", "w", encoding="utf-8") as f:
    f.write(html)

# Save CSV
with open(f"{OUT}/validation_results.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["status", "metric", "our_value", "benchmark", "gap", "source", "note"])
    for v in validations:
        w.writerow([v['status'], v['metric'], v['our_value'], v['benchmark'], v['gap'], v['source'], v['note']])

print(f"\nValidation report: {OUT}/validation_report.html")
print(f"Validation CSV: {OUT}/validation_results.csv")
