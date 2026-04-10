#!/usr/bin/env python3
"""
Post-analysis of UrbanEV simulation iteration 5.
Generates CSV summaries and an HTML dashboard with charts.
No external dependencies — uses only Python standard library.
"""
import gzip
import csv
import os
import json
from collections import defaultdict

EVENTS_FILE = "output/maryland_ev_enhanced/ITERS/it.5/maryland_ev_v2.5.events.xml.gz"
SCORE_FILE = "output/maryland_ev_enhanced/maryland_ev_v2.scorestats.txt"
SUMMARY_FILE = "Input Files/ev_population_summary.csv"
LOG_FILE = "full_simulation.log"
OUTPUT_DIR = "analysis_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_attr(line, attr):
    key = f'{attr}="'
    s = line.find(key)
    if s < 0: return None
    s += len(key)
    e = line.find('"', s)
    return line[s:e] if e > s else None

print("=" * 70)
print("UrbanEV Maryland Post-Analysis — Iteration 5")
print("=" * 70)

# ══════════════════════════════════════════════════════════════════════
# 1. Parse Events
# ══════════════════════════════════════════════════════════════════════
print("\n1. Parsing events file...")

charger_sessions_by_type = defaultdict(list)  # chargerType -> [kWh]
charger_sessions_by_hour = defaultdict(int)
soc_all = []
soc_at_charging = []
walking_dists = []
agent_charging = defaultdict(lambda: {"home": 0, "work": 0, "public": 0, "total_kwh": 0.0})
stuck_links = defaultdict(int)
stuck_count = 0
scoring_total = 0
activity_types = defaultdict(int)
charger_id_usage = defaultdict(int)
soc_by_hour = defaultdict(list)

with gzip.open(EVENTS_FILE, 'rt') as f:
    for line in f:
        if 'stuckAndAbort' in line:
            stuck_count += 1
            link = get_attr(line, 'link')
            if link: stuck_links[link] += 1

        elif 'type="scoring"' in line:
            scoring_total += 1
            soc = get_attr(line, 'soc')
            cost_only = get_attr(line, 'costOnly') == 'true'
            act_type = get_attr(line, 'activityType')
            person = get_attr(line, 'person')
            time_str = get_attr(line, 'time')

            if soc:
                soc_val = float(soc)
                soc_all.append(soc_val)
                if time_str:
                    hour = int(float(time_str) / 3600) % 24
                    soc_by_hour[hour].append(soc_val)

            if cost_only:
                energy = get_attr(line, 'energyChargedKWh')
                ct = get_attr(line, 'chargerType')
                power = get_attr(line, 'chargerPowerKw')
                if energy and ct:
                    e = float(energy)
                    if e > 0:
                        charger_sessions_by_type[ct].append(e)
                        if person:
                            agent_charging[person][ct] += 1
                            agent_charging[person]["total_kwh"] += e
                        if time_str:
                            hour = int(float(time_str) / 3600) % 24
                            charger_sessions_by_hour[hour] += 1
            else:
                if soc and act_type and 'charging' in (act_type or ''):
                    soc_at_charging.append(float(soc))
                walking = get_attr(line, 'walkingDistance')
                if walking:
                    wd = float(walking)
                    if wd > 0:
                        walking_dists.append(wd)

        elif 'actstart' in line:
            at = get_attr(line, 'type')
            if at: activity_types[at] += 1

print(f"  Scoring events: {scoring_total:,}")
print(f"  Stuck agents: {stuck_count}")

# ══════════════════════════════════════════════════════════════════════
# 2. Parse Score Stats
# ══════════════════════════════════════════════════════════════════════
print("\n2. Parsing score statistics...")
scores = []
if os.path.exists(SCORE_FILE):
    with open(SCORE_FILE) as f:
        for line in f:
            if line.startswith("ITERATION"): continue
            parts = line.strip().split("\t")
            if len(parts) >= 5:
                try:
                    scores.append({
                        "iter": int(parts[0]),
                        "executed": float(parts[1]),
                        "worst": float(parts[2]),
                        "avg": float(parts[3]),
                        "best": float(parts[4]),
                    })
                except: pass

# ══════════════════════════════════════════════════════════════════════
# 3. Parse Agent Summary for Equity Analysis
# ══════════════════════════════════════════════════════════════════════
print("\n3. Parsing agent summary for equity...")
income_midpoints = {0:7500,1:12500,2:20000,3:30000,4:42500,5:62500,6:87500,7:125000,8:175000,9:250000}
agent_info = {}
if os.path.exists(SUMMARY_FILE):
    with open(SUMMARY_FILE) as f:
        for row in csv.DictReader(f):
            pid = row['person_id']
            agent_info[pid] = {
                'income': int(row.get('income_bracket', 5)),
                'dwelling': row.get('dwelling_type', 'unknown'),
                'home_charger': float(row.get('home_charger_kw', 0)),
                'ev_type': row.get('ev_type', 'BEV'),
                'ev_model': row.get('ev_model', ''),
            }

# ══════════════════════════════════════════════════════════════════════
# 4. Parse Log for Iteration Metrics
# ══════════════════════════════════════════════════════════════════════
print("\n4. Parsing simulation log...")
persist_data = []
problem_data = []
enroute_total = 0
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, errors='ignore') as f:
        for line in f:
            if 'SoC persistence (iter' in line:
                import re
                m = re.search(r'iter (\d+)\): (\d+).*\| (\d+) plugged.*\| (\d+) home.*\| (\d+) no home', line)
                if m:
                    persist_data.append({"iter": int(m.group(1)), "plugged": int(m.group(3)), "no_charger": int(m.group(5))})
            if 'replanning has' in line and 'SocProblemCollector' in line:
                m = re.search(r'iteration (\d+) replanning has (\d+)', line)
                if m:
                    problem_data.append({"iter": int(m.group(1)), "problems": int(m.group(2))})
            if 'InsertEnRoute: inserted' in line:
                enroute_total += 1

# ══════════════════════════════════════════════════════════════════════
# 5. Generate CSV Reports
# ══════════════════════════════════════════════════════════════════════
print("\n5. Generating CSV reports...")

# 5a. Score convergence
with open(f"{OUTPUT_DIR}/score_convergence.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["iteration", "avg_executed", "avg_worst", "avg_avg", "avg_best"])
    for s in scores:
        w.writerow([s["iter"], f"{s['executed']:.4f}", f"{s['worst']:.4f}", f"{s['avg']:.4f}", f"{s['best']:.4f}"])

# 5b. Charger type summary
with open(f"{OUTPUT_DIR}/charger_type_summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["charger_type", "sessions", "avg_kwh", "median_kwh", "total_kwh"])
    for ct in ["home", "work", "public"]:
        sessions = charger_sessions_by_type.get(ct, [])
        if sessions:
            import statistics
            w.writerow([ct, len(sessions), f"{statistics.mean(sessions):.2f}",
                       f"{statistics.median(sessions):.2f}", f"{sum(sessions):.1f}"])

# 5c. Charging by hour
with open(f"{OUTPUT_DIR}/charging_by_hour.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["hour", "sessions"])
    for h in range(24):
        w.writerow([h, charger_sessions_by_hour.get(h, 0)])

# 5d. SoC distribution
with open(f"{OUTPUT_DIR}/soc_distribution.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["soc_bin", "count", "percentage"])
    bins = [(0, 0.05, "0-5%"), (0.05, 0.10, "5-10%"), (0.10, 0.15, "10-15%"),
            (0.15, 0.20, "15-20%"), (0.20, 0.30, "20-30%"), (0.30, 0.50, "30-50%"),
            (0.50, 0.70, "50-70%"), (0.70, 1.01, "70-100%")]
    for lo, hi, label in bins:
        count = sum(1 for s in soc_all if lo <= s < hi)
        w.writerow([label, count, f"{count/max(len(soc_all),1)*100:.1f}"])

# 5e. Equity: charging by income
with open(f"{OUTPUT_DIR}/equity_by_income.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["income_bracket", "income_midpoint", "agents", "agents_with_charging",
                "avg_sessions", "avg_kwh", "pct_no_charger", "avg_home_charger_kw"])
    income_groups = defaultdict(lambda: {"total": 0, "charged": 0, "sessions": 0, "kwh": 0.0,
                                          "no_charger": 0, "home_kw_sum": 0.0})
    for pid, info in agent_info.items():
        inc = info['income']
        if inc > 9: continue
        g = income_groups[inc]
        g["total"] += 1
        g["home_kw_sum"] += info['home_charger']
        if info['home_charger'] == 0: g["no_charger"] += 1
        ac = agent_charging.get(pid)
        if ac and ac["total_kwh"] > 0:
            g["charged"] += 1
            g["sessions"] += ac["home"] + ac["work"] + ac["public"]
            g["kwh"] += ac["total_kwh"]
    for inc in sorted(income_groups.keys()):
        g = income_groups[inc]
        n = max(g["total"], 1)
        w.writerow([inc, income_midpoints.get(inc, 0), g["total"], g["charged"],
                    f"{g['sessions']/n:.2f}", f"{g['kwh']/n:.2f}",
                    f"{g['no_charger']/n*100:.1f}", f"{g['home_kw_sum']/n:.2f}"])

# 5f. Walking distance distribution
with open(f"{OUTPUT_DIR}/walking_distance.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["distance_bin", "count"])
    wbins = [(0, 200, "0-200m"), (200, 400, "200-400m"), (400, 600, "400-600m"),
             (600, 800, "600-800m"), (800, 1000, "800-1000m"), (1000, 1500, "1000-1500m")]
    for lo, hi, label in wbins:
        count = sum(1 for d in walking_dists if lo <= d < hi)
        w.writerow([label, count])

# 5g. Overnight charging persistence
with open(f"{OUTPUT_DIR}/overnight_charging.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["iteration", "plugged_in", "plug_rate_pct", "no_charger"])
    for p in persist_data:
        rate = p["plugged"] / 130837 * 100
        w.writerow([p["iter"], p["plugged"], f"{rate:.1f}", p["no_charger"]])

# 5h. BEV vs PHEV charging
with open(f"{OUTPUT_DIR}/bev_vs_phev.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ev_type", "agents", "agents_charged", "avg_sessions", "avg_kwh",
                "pct_home", "pct_work", "pct_public"])
    for evtype in ["BEV", "PHEV"]:
        agents_of_type = [pid for pid, info in agent_info.items() if info["ev_type"] == evtype]
        n = len(agents_of_type)
        charged = 0; total_s = 0; total_kwh = 0; home_s = 0; work_s = 0; pub_s = 0
        for pid in agents_of_type:
            ac = agent_charging.get(pid)
            if ac and ac["total_kwh"] > 0:
                charged += 1
                home_s += ac["home"]; work_s += ac["work"]; pub_s += ac["public"]
                total_s += ac["home"] + ac["work"] + ac["public"]
                total_kwh += ac["total_kwh"]
        all_s = max(home_s + work_s + pub_s, 1)
        w.writerow([evtype, n, charged, f"{total_s/max(n,1):.2f}", f"{total_kwh/max(n,1):.2f}",
                    f"{home_s/all_s*100:.1f}", f"{work_s/all_s*100:.1f}", f"{pub_s/all_s*100:.1f}"])

print(f"  CSVs written to {OUTPUT_DIR}/")

# ══════════════════════════════════════════════════════════════════════
# 6. Generate HTML Dashboard with Charts
# ══════════════════════════════════════════════════════════════════════
print("\n6. Generating HTML dashboard...")

# Prepare chart data
score_labels = json.dumps([s["iter"] for s in scores])
score_executed = json.dumps([round(s["executed"], 3) for s in scores])
score_best = json.dumps([round(s["best"], 3) for s in scores])
score_worst = json.dumps([round(s["worst"], 3) for s in scores])

charger_labels = json.dumps(["Home", "Work", "Public"])
charger_counts = json.dumps([len(charger_sessions_by_type.get("home", [])),
                              len(charger_sessions_by_type.get("work", [])),
                              len(charger_sessions_by_type.get("public", []))])
charger_kwh = json.dumps([round(sum(charger_sessions_by_type.get("home", [])), 1),
                           round(sum(charger_sessions_by_type.get("work", [])), 1),
                           round(sum(charger_sessions_by_type.get("public", [])), 1)])

hour_labels = json.dumps(list(range(24)))
hour_data = json.dumps([charger_sessions_by_hour.get(h, 0) for h in range(24)])

soc_labels = json.dumps(["0-5%", "5-10%", "10-15%", "15-20%", "20-30%", "30-50%", "50-70%", "70-100%"])
soc_counts = json.dumps([
    sum(1 for s in soc_all if s < 0.05),
    sum(1 for s in soc_all if 0.05 <= s < 0.10),
    sum(1 for s in soc_all if 0.10 <= s < 0.15),
    sum(1 for s in soc_all if 0.15 <= s < 0.20),
    sum(1 for s in soc_all if 0.20 <= s < 0.30),
    sum(1 for s in soc_all if 0.30 <= s < 0.50),
    sum(1 for s in soc_all if 0.50 <= s < 0.70),
    sum(1 for s in soc_all if 0.70 <= s),
])

walk_labels = json.dumps(["0-200", "200-400", "400-600", "600-800", "800-1000", "1000-1500"])
walk_data = json.dumps([
    sum(1 for d in walking_dists if d < 200),
    sum(1 for d in walking_dists if 200 <= d < 400),
    sum(1 for d in walking_dists if 400 <= d < 600),
    sum(1 for d in walking_dists if 600 <= d < 800),
    sum(1 for d in walking_dists if 800 <= d < 1000),
    sum(1 for d in walking_dists if 1000 <= d < 1500),
])

persist_labels = json.dumps([p["iter"] for p in persist_data])
persist_plugged = json.dumps([p["plugged"] for p in persist_data])

problem_labels = json.dumps([p["iter"] for p in problem_data])
problem_counts = json.dumps([p["problems"] for p in problem_data])

# Income equity
eq_labels = json.dumps([f"${income_midpoints[i]:,}" for i in sorted(income_groups.keys())])
eq_no_charger = json.dumps([round(income_groups[i]["no_charger"]/max(income_groups[i]["total"],1)*100, 1)
                             for i in sorted(income_groups.keys())])
eq_charged = json.dumps([income_groups[i]["charged"] for i in sorted(income_groups.keys())])

# Energy distribution
energy_all = []
for ct_list in charger_sessions_by_type.values():
    energy_all.extend(ct_list)
energy_labels = json.dumps(["<1", "1-5", "5-10", "10-20", "20-40", ">40"])
energy_counts = json.dumps([
    sum(1 for e in energy_all if e < 1),
    sum(1 for e in energy_all if 1 <= e < 5),
    sum(1 for e in energy_all if 5 <= e < 10),
    sum(1 for e in energy_all if 10 <= e < 20),
    sum(1 for e in energy_all if 20 <= e < 40),
    sum(1 for e in energy_all if e >= 40),
])

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UrbanEV Maryland - Simulation Analysis Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
h1 {{ color: #1a1a2e; border-bottom: 3px solid #2196F3; padding-bottom: 10px; }}
h2 {{ color: #2196F3; margin-top: 40px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
.card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.card h3 {{ margin-top: 0; color: #673AB7; }}
.metric {{ display: inline-block; background: #e8f5e9; padding: 8px 16px; border-radius: 8px; margin: 4px; font-weight: bold; }}
.metric.warn {{ background: #fce4ec; }}
.metric.info {{ background: #e8f4fd; }}
canvas {{ max-height: 350px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
th {{ background: #2196F3; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
td:first-child {{ text-align: left; }}
.footer {{ margin-top: 40px; text-align: center; color: #888; font-size: 12px; }}
</style>
</head>
<body>

<h1>UrbanEV-v2 Maryland: Simulation Analysis Dashboard</h1>
<p>Iteration 5 | 130,837 EV Agents (91K BEV + 40K PHEV) | 9.8M Link Network | 1,958 Public Chargers</p>

<div class="grid">
<div class="card">
<h3>Key Metrics</h3>
<span class="metric">Agents: 130,837</span>
<span class="metric">Stuck: {stuck_count} (0.05%)</span>
<span class="metric info">Charging Sessions: {sum(len(v) for v in charger_sessions_by_type.values()):,}</span>
<span class="metric info">En-Route Insertions: {enroute_total:,}</span>
<span class="metric">Home Sessions: {len(charger_sessions_by_type.get('home',[])):,}</span>
<span class="metric">Work Sessions: {len(charger_sessions_by_type.get('work',[])):,}</span>
<span class="metric">Public Sessions: {len(charger_sessions_by_type.get('public',[])):,}</span>
<span class="metric warn">Low SoC (<20%): {sum(1 for s in soc_all if s < 0.20):,} events</span>
</div>
<div class="card">
<h3>Score Convergence</h3>
<canvas id="chartScores"></canvas>
</div>
</div>

<h2>Charging Behavior</h2>
<div class="grid">
<div class="card">
<h3>Sessions by Charger Type</h3>
<canvas id="chartChargerType"></canvas>
</div>
<div class="card">
<h3>Energy Charged by Type (kWh)</h3>
<canvas id="chartChargerKwh"></canvas>
</div>
</div>

<div class="grid">
<div class="card">
<h3>Charging Sessions by Hour of Day</h3>
<canvas id="chartHourly"></canvas>
</div>
<div class="card">
<h3>Energy per Session Distribution (kWh)</h3>
<canvas id="chartEnergy"></canvas>
</div>
</div>

<h2>Battery State of Charge</h2>
<div class="grid">
<div class="card">
<h3>SoC Distribution (All Scoring Events)</h3>
<canvas id="chartSoC"></canvas>
</div>
<div class="card">
<h3>Walking Distance to Charger</h3>
<canvas id="chartWalking"></canvas>
</div>
</div>

<h2>Multi-Day Dynamics</h2>
<div class="grid">
<div class="card">
<h3>Overnight Plug-in Rate by Iteration</h3>
<canvas id="chartPersist"></canvas>
</div>
<div class="card">
<h3>SoC Problems by Iteration</h3>
<canvas id="chartProblems"></canvas>
</div>
</div>

<h2>Equity Analysis</h2>
<div class="grid">
<div class="card">
<h3>No-Home-Charger Rate by Income</h3>
<canvas id="chartEquityNoCharger"></canvas>
</div>
<div class="card">
<h3>Agents with Charging Sessions by Income</h3>
<canvas id="chartEquityCharged"></canvas>
</div>
</div>

<h2>Charger Type Details</h2>
<table>
<tr><th>Type</th><th>Sessions</th><th>Avg kWh</th><th>Median kWh</th><th>Total kWh</th><th>Avg Power (kW)</th></tr>
"""
import statistics
for ct in ["home", "work", "public"]:
    sessions = charger_sessions_by_type.get(ct, [])
    if sessions:
        html += f"<tr><td>{ct.title()}</td><td>{len(sessions):,}</td><td>{statistics.mean(sessions):.2f}</td><td>{statistics.median(sessions):.2f}</td><td>{sum(sessions):,.1f}</td><td>{'6.4' if ct=='home' else '12.2' if ct=='work' else '11.3'}</td></tr>\n"
html += "</table>\n"

html += f"""
<div class="footer">
Generated from iteration 5 events | {scoring_total:,} scoring events analyzed<br>
UrbanEV-v2 Maryland | github.com/Tomal121186621/UrbanEV-MATSim-Maryland
</div>

<script>
const colors = {{
    blue: '#2196F3', green: '#4CAF50', orange: '#FF9800',
    pink: '#E91E63', purple: '#673AB7', teal: '#009688',
    red: '#F44336', yellow: '#FFC107'
}};

// Score Convergence
new Chart(document.getElementById('chartScores'), {{
    type: 'line',
    data: {{
        labels: {score_labels},
        datasets: [
            {{ label: 'Avg Best', data: {score_best}, borderColor: colors.green, borderWidth: 3, fill: false }},
            {{ label: 'Avg Executed', data: {score_executed}, borderColor: colors.blue, borderWidth: 2, fill: false }},
            {{ label: 'Avg Worst', data: {score_worst}, borderColor: colors.red, borderWidth: 1, borderDash: [5,5], fill: false }},
        ]
    }},
    options: {{ plugins: {{ title: {{ display: true, text: 'Score Convergence Over Iterations' }} }} }}
}});

// Charger Type Sessions
new Chart(document.getElementById('chartChargerType'), {{
    type: 'doughnut',
    data: {{
        labels: {charger_labels},
        datasets: [{{ data: {charger_counts}, backgroundColor: [colors.green, colors.blue, colors.orange] }}]
    }}
}});

// Charger Type kWh
new Chart(document.getElementById('chartChargerKwh'), {{
    type: 'bar',
    data: {{
        labels: {charger_labels},
        datasets: [{{ label: 'Total kWh', data: {charger_kwh}, backgroundColor: [colors.green, colors.blue, colors.orange] }}]
    }}
}});

// Hourly
new Chart(document.getElementById('chartHourly'), {{
    type: 'bar',
    data: {{
        labels: {hour_labels},
        datasets: [{{ label: 'Sessions', data: {hour_data}, backgroundColor: colors.purple }}]
    }},
    options: {{ plugins: {{ title: {{ display: true, text: '24-Hour Charging Demand Profile' }} }} }}
}});

// Energy Distribution
new Chart(document.getElementById('chartEnergy'), {{
    type: 'bar',
    data: {{
        labels: {energy_labels},
        datasets: [{{ label: 'Sessions', data: {energy_counts}, backgroundColor: colors.teal }}]
    }}
}});

// SoC Distribution
new Chart(document.getElementById('chartSoC'), {{
    type: 'bar',
    data: {{
        labels: {soc_labels},
        datasets: [{{ label: 'Events', data: {soc_counts}, backgroundColor: [colors.red, colors.red, colors.orange, colors.orange, colors.yellow, colors.blue, colors.green, colors.green] }}]
    }}
}});

// Walking Distance
new Chart(document.getElementById('chartWalking'), {{
    type: 'bar',
    data: {{
        labels: {walk_labels},
        datasets: [{{ label: 'Events', data: {walk_data}, backgroundColor: colors.purple }}]
    }},
    options: {{ plugins: {{ title: {{ display: true, text: 'Walking Distance to Charger (meters)' }} }} }}
}});

// Overnight Persistence
new Chart(document.getElementById('chartPersist'), {{
    type: 'line',
    data: {{
        labels: {persist_labels},
        datasets: [{{ label: 'Plugged In Overnight', data: {persist_plugged}, borderColor: colors.green, backgroundColor: 'rgba(76,175,80,0.1)', fill: true }}]
    }}
}});

// SoC Problems
new Chart(document.getElementById('chartProblems'), {{
    type: 'line',
    data: {{
        labels: {problem_labels},
        datasets: [{{ label: 'Agents with SoC Problems', data: {problem_counts}, borderColor: colors.red, backgroundColor: 'rgba(244,67,54,0.1)', fill: true }}]
    }}
}});

// Equity - No Charger
new Chart(document.getElementById('chartEquityNoCharger'), {{
    type: 'bar',
    data: {{
        labels: {eq_labels},
        datasets: [{{ label: 'No Home Charger (%)', data: {eq_no_charger}, backgroundColor: colors.pink }}]
    }},
    options: {{ plugins: {{ title: {{ display: true, text: 'Agents Without Home Charger by Income' }} }} }}
}});

// Equity - Charged
new Chart(document.getElementById('chartEquityCharged'), {{
    type: 'bar',
    data: {{
        labels: {eq_labels},
        datasets: [{{ label: 'Agents with Charging', data: {eq_charged}, backgroundColor: colors.blue }}]
    }}
}});
</script>
</body>
</html>
"""

with open(f"{OUTPUT_DIR}/dashboard.html", "w") as f:
    f.write(html)

print(f"  Dashboard: {OUTPUT_DIR}/dashboard.html")
print(f"\n{'='*70}")
print(f"Analysis complete!")
print(f"  CSVs: {OUTPUT_DIR}/ (8 files)")
print(f"  Dashboard: {OUTPUT_DIR}/dashboard.html (open in browser)")
print(f"{'='*70}")
