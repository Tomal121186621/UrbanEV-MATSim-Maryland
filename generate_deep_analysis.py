#!/usr/bin/env python3
"""
Deep post-analysis extracting maximum insight from 298M events.
Focuses on: grid load curves, charger utilization, individual agent trajectories,
charging session economics, spatial gaps, BEV vs PHEV behavior.
"""
import gzip
import csv
import os
import json
import math
from collections import defaultdict

EVENTS = "output/maryland_ev_enhanced/ITERS/it.5/maryland_ev_v2.5.events.xml.gz"
CHARGERS = "Input Files/chargers.xml"
SUMMARY = "Input Files/ev_population_summary.csv"
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

def sp2ll(x, y):
    return round(39.0 + (y-150000)/111000, 5), round(-76.7 + (x-400000)/85000, 5)

print("=" * 70)
print("DEEP ANALYSIS: 298M Events")
print("=" * 70)

# ── Load charger info ──
charger_info = {}
with open(CHARGERS) as f:
    for line in f:
        if '<charger ' not in line: continue
        cid = ga(line, 'id')
        charger_info[cid] = {
            'x': float(ga(line,'x') or 0), 'y': float(ga(line,'y') or 0),
            'type': ga(line,'type'), 'power': float(ga(line,'plug_power') or 0),
            'plugs': int(ga(line,'plug_count') or 1)
        }

# ── Load agent info ──
agent_info = {}
with open(SUMMARY) as f:
    for row in csv.DictReader(f):
        agent_info[row['person_id']] = {
            'income': int(row.get('income_bracket',5)),
            'hc_kw': float(row.get('home_charger_kw',0)),
            'ev_type': row.get('ev_type','BEV'),
            'ev_model': row.get('ev_model',''),
            'dwelling': row.get('dwelling_type',''),
            'home_x': float(row.get('home_x',0)),
            'home_y': float(row.get('home_y',0)),
        }

income_mp = {0:7500,1:12500,2:20000,3:30000,4:42500,5:62500,6:87500,7:125000,8:175000,9:250000}

# ── Parse events ──
print("\nParsing 298M events (this takes a few minutes)...")

# Grid load: kW drawn per 15-min interval
grid_load = defaultdict(float)  # time_bucket -> kW
grid_load_home = defaultdict(float)
grid_load_work = defaultdict(float)
grid_load_public = defaultdict(float)

# Charger utilization: per charger sessions and duration
charger_sessions = defaultdict(int)
charger_duration = defaultdict(float)  # seconds
charger_energy = defaultdict(float)  # kWh from scoring events

# Agent daily SoC trajectory (sample 10 agents)
sample_agents = set()
agent_soc_trace = defaultdict(list)  # pid -> [(time, soc)]

# Charging session details
sessions = []  # (pid, charger_id, charger_type, start_time, duration, soc_start, soc_end)
active_sessions = {}  # vehicle_id -> {charger, start_time, type}

# No-charger locations (from scoring events with charging failed)
no_charger_locations = []

# Trip distances
trip_distances = []

# Activity locations for spatial analysis
charging_activity_locs = []

count = 0
with gzip.open(EVENTS, 'rt') as f:
    for line in f:
        count += 1
        if count % 50000000 == 0:
            print(f"  {count/1000000:.0f}M events processed...")

        if 'charging_start' in line and 'type="charging_start"' in line:
            cid = ga(line, 'charger')
            vid = ga(line, 'vehicle')
            ct = ga(line, 'chargerType')
            t = float(ga(line, 'time') or 0)
            active_sessions[vid] = {'charger': cid, 'start': t, 'type': ct}
            charger_sessions[cid] += 1

            # Grid load: add power draw
            if cid in charger_info:
                power_kw = charger_info[cid]['power']
                bucket = int(t / 900)  # 15-min buckets
                grid_load[bucket] += power_kw
                if '_home' in cid: grid_load_home[bucket] += power_kw
                elif 'workplace_' in cid: grid_load_work[bucket] += power_kw
                else: grid_load_public[bucket] += power_kw

        elif 'charging_end' in line and 'type="charging_end"' in line:
            cid = ga(line, 'charger')
            vid = ga(line, 'vehicle')
            t = float(ga(line, 'time') or 0)
            dur = float(ga(line, 'charging_duration') or 0)
            soc_end = float(ga(line, 'soc') or 0)
            charger_duration[cid] += dur

            if vid in active_sessions:
                sess = active_sessions.pop(vid)
                sessions.append({
                    'person': vid, 'charger': sess['charger'],
                    'type': sess['type'], 'start': sess['start'],
                    'duration': dur, 'soc_end': soc_end,
                    'hour': int(sess['start'] / 3600) % 24,
                })

                # Remove grid load
                if cid in charger_info:
                    power_kw = charger_info[cid]['power']
                    bucket = int(t / 900)
                    grid_load[bucket] -= power_kw

        elif 'unplugging' in line and 'type="unplugging"' in line:
            pass  # duration info already in charging_end

        elif 'type="scoring"' in line:
            pid = ga(line, 'person')
            soc = ga(line, 'soc')
            t = ga(line, 'time')
            act = ga(line, 'activityType')

            # Sample agent SoC traces
            if pid and soc and t:
                if len(sample_agents) < 20:
                    sample_agents.add(pid)
                if pid in sample_agents:
                    agent_soc_trace[pid].append((float(t), float(soc)))

            # No-charger locations
            if act and 'failed' in act:
                link = ga(line, 'link')
                if link:
                    no_charger_locations.append({'person': pid, 'act': act})

            # Charging session energy
            if ga(line, 'costOnly') == 'true':
                energy = ga(line, 'energyChargedKWh')
                ct = ga(line, 'chargerType')
                if energy and ct:
                    e = float(energy)
                    if e > 0:
                        charger_energy[ct] += e

        elif 'actstart' in line:
            act = ga(line, 'type')
            x = ga(line, 'x')
            y = ga(line, 'y')
            if act and 'charging' in (act or '') and x and y:
                charging_activity_locs.append({
                    'x': float(x), 'y': float(y), 'type': act,
                    'success': 'failed' not in act
                })

        elif 'type="travelled"' in line:
            dist = ga(line, 'distance')
            if dist:
                trip_distances.append(float(dist))

print(f"  Done. {count:,} events processed.")
print(f"  {len(sessions):,} charging sessions")
print(f"  {len(charging_activity_locs):,} charging activity locations")

# ══════════════════════════════════════════════════════════════════════
# Analysis Computations
# ══════════════════════════════════════════════════════════════════════

# Grid load curve: convert to hourly kW
hourly_grid = defaultdict(float)
hourly_home_grid = defaultdict(float)
hourly_work_grid = defaultdict(float)
hourly_public_grid = defaultdict(float)

for sess in sessions:
    h = sess['hour']
    power = 7.2  # default
    if sess['charger'] in charger_info:
        power = charger_info[sess['charger']]['power']
    # Approximate: add power for duration fraction of that hour
    dur_hours = sess['duration'] / 3600
    energy = power * dur_hours
    hourly_grid[h] += energy
    cid = sess['charger']
    if '_home' in cid: hourly_home_grid[h] += energy
    elif 'workplace_' in cid: hourly_work_grid[h] += energy
    else: hourly_public_grid[h] += energy

# Charger utilization rate (top chargers)
sim_duration = 240 * 3600  # 240 hours
charger_util = {}
for cid, dur in charger_duration.items():
    if cid in charger_info:
        plugs = charger_info[cid]['plugs']
        max_capacity = sim_duration * plugs
        util_rate = min(dur / max_capacity, 1.0) if max_capacity > 0 else 0
        charger_util[cid] = {
            'util': util_rate,
            'sessions': charger_sessions.get(cid, 0),
            'hours': dur / 3600,
            'type': charger_info[cid]['type'],
            'power': charger_info[cid]['power'],
            'plugs': plugs,
            'x': charger_info[cid]['x'],
            'y': charger_info[cid]['y'],
        }

# Session duration by charger type
dur_by_type = defaultdict(list)
for s in sessions:
    dur_by_type[s['type']].append(s['duration'] / 60)  # minutes

# Income-stratified charging cost
income_charging = defaultdict(lambda: {'sessions': 0, 'kwh': 0, 'home': 0, 'work': 0, 'public': 0, 'agents': 0})
agent_session_count = defaultdict(lambda: {'home': 0, 'work': 0, 'public': 0, 'kwh': 0})
for s in sessions:
    pid = s['person']
    cid = s['charger']
    if '_home' in cid: agent_session_count[pid]['home'] += 1
    elif 'workplace_' in cid: agent_session_count[pid]['work'] += 1
    else: agent_session_count[pid]['public'] += 1

for pid, info in agent_info.items():
    inc = info['income']
    if inc > 9: continue
    sc = agent_session_count.get(pid, {'home':0,'work':0,'public':0,'kwh':0})
    g = income_charging[inc]
    g['agents'] += 1
    g['sessions'] += sc['home'] + sc['work'] + sc['public']
    g['home'] += sc['home']
    g['work'] += sc['work']
    g['public'] += sc['public']

# BEV vs PHEV session comparison
bev_phev = defaultdict(lambda: {'agents': 0, 'sessions': 0, 'avg_dur': [], 'types': defaultdict(int)})
for pid, info in agent_info.items():
    et = info['ev_type']
    bev_phev[et]['agents'] += 1
for s in sessions:
    pid = s['person']
    if pid in agent_info:
        et = agent_info[pid]['ev_type']
        bev_phev[et]['sessions'] += 1
        bev_phev[et]['avg_dur'].append(s['duration']/60)
        bev_phev[et]['types'][s['type']] += 1

# ══════════════════════════════════════════════════════════════════════
# Generate HTML Dashboard
# ══════════════════════════════════════════════════════════════════════
print("\nGenerating deep analysis dashboard...")

# Prepare data for charts
h_labels = json.dumps(list(range(24)))
h_home = json.dumps([round(hourly_home_grid.get(h,0),1) for h in range(24)])
h_work = json.dumps([round(hourly_work_grid.get(h,0),1) for h in range(24)])
h_public = json.dumps([round(hourly_public_grid.get(h,0),1) for h in range(24)])

# Agent SoC traces (first 6)
trace_datasets = ""
colors_list = ['#2196F3','#E91E63','#4CAF50','#FF9800','#673AB7','#009688']
trace_agents = list(agent_soc_trace.keys())[:6]
for i, pid in enumerate(trace_agents):
    points = agent_soc_trace[pid]
    # Sample to max 50 points
    step = max(1, len(points) // 50)
    sampled = points[::step]
    x_data = [round(p[0]/3600, 2) for p in sampled]
    y_data = [round(p[1]*100, 1) for p in sampled]
    color = colors_list[i % len(colors_list)]
    info = agent_info.get(pid, {})
    label = f"{pid} ({info.get('ev_type','?')}, ${income_mp.get(info.get('income',5),62500):,})"
    trace_datasets += f"{{ label: '{label}', data: {json.dumps([{'x':x,'y':y} for x,y in zip(x_data, y_data)])}, borderColor: '{color}', borderWidth: 1.5, fill: false, pointRadius: 0 }},\n"

# Top utilized chargers
top_util = sorted(charger_util.items(), key=lambda x: -x[1]['sessions'])[:30]
util_map_data = []
for cid, u in top_util:
    lat, lon = sp2ll(u['x'], u['y'])
    util_map_data.append({
        'lat': lat, 'lon': lon, 'id': cid, 'type': u['type'],
        'util': round(u['util']*100, 1), 'sessions': u['sessions'],
        'hours': round(u['hours'], 1), 'power': u['power'], 'plugs': u['plugs']
    })

# Charging gap locations (failed activities)
gap_locs = []
for loc in charging_activity_locs:
    if not loc['success']:
        lat, lon = sp2ll(loc['x'], loc['y'])
        gap_locs.append({'lat': lat, 'lon': lon, 'type': loc['type']})
# Sample to max 500
if len(gap_locs) > 500:
    import random
    random.seed(42)
    gap_locs = random.sample(gap_locs, 500)

# Session duration histogram data
dur_home = dur_by_type.get('L2', []) + dur_by_type.get('L1', [])
dur_labels_hist = json.dumps(["<5", "5-15", "15-30", "30-60", "60-120", "120-240", ">240"])
dur_home_h = json.dumps([sum(1 for d in dur_home if d<5), sum(1 for d in dur_home if 5<=d<15),
    sum(1 for d in dur_home if 15<=d<30), sum(1 for d in dur_home if 30<=d<60),
    sum(1 for d in dur_home if 60<=d<120), sum(1 for d in dur_home if 120<=d<240),
    sum(1 for d in dur_home if d>=240)])

# Income equity data
inc_labels = json.dumps([f"${income_mp[i]:,}" for i in sorted(income_charging.keys()) if i <= 9])
inc_sessions = json.dumps([round(income_charging[i]['sessions']/max(income_charging[i]['agents'],1),2) for i in sorted(income_charging.keys()) if i <= 9])
inc_home_pct = json.dumps([round(income_charging[i]['home']/max(income_charging[i]['sessions'],1)*100,1) for i in sorted(income_charging.keys()) if i <= 9])
inc_public_pct = json.dumps([round(income_charging[i]['public']/max(income_charging[i]['sessions'],1)*100,1) for i in sorted(income_charging.keys()) if i <= 9])

# BEV vs PHEV comparison
bp_labels = json.dumps(['BEV', 'PHEV'])
bp_sessions = json.dumps([bev_phev['BEV']['sessions'], bev_phev['PHEV']['sessions']])
import statistics
bp_avg_dur = json.dumps([
    round(statistics.mean(bev_phev['BEV']['avg_dur']),1) if bev_phev['BEV']['avg_dur'] else 0,
    round(statistics.mean(bev_phev['PHEV']['avg_dur']),1) if bev_phev['PHEV']['avg_dur'] else 0,
])

# Trip distance histogram
td_labels = json.dumps(["<2km","2-5km","5-10km","10-20km","20-50km",">50km"])
td_counts = json.dumps([
    sum(1 for d in trip_distances if d<2000),
    sum(1 for d in trip_distances if 2000<=d<5000),
    sum(1 for d in trip_distances if 5000<=d<10000),
    sum(1 for d in trip_distances if 10000<=d<20000),
    sum(1 for d in trip_distances if 20000<=d<50000),
    sum(1 for d in trip_distances if d>=50000),
])

# Energy totals
total_home_kwh = round(charger_energy.get('home', 0), 0)
total_work_kwh = round(charger_energy.get('work', 0), 0)
total_public_kwh = round(charger_energy.get('public', 0), 0)
total_kwh = total_home_kwh + total_work_kwh + total_public_kwh

html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>UrbanEV Maryland - Deep Analysis</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body{{font-family:'Segoe UI',sans-serif;margin:0;padding:20px;background:#f0f2f5;color:#333}}
h1{{color:#1a1a2e;border-bottom:3px solid #E91E63;padding-bottom:10px}}
h2{{color:#E91E63;margin-top:40px;border-left:4px solid #E91E63;padding-left:12px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;margin:20px 0}}
.g4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:15px;margin:20px 0}}
.c{{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08)}}
.c h3{{margin-top:0;color:#673AB7;font-size:14px}}
canvas{{max-height:300px}}
.sb{{padding:15px;border-radius:12px;text-align:center;color:white}}
.sb .n{{font-size:24px;font-weight:bold}}.sb .l{{font-size:11px;opacity:0.85}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #e0e0e0;padding:6px 10px;text-align:right}}
th{{background:#673AB7;color:white}}td:first-child{{text-align:left}}
tr:nth-child(even){{background:#fafafa}}
#mapUtil,#mapGaps{{height:400px;border-radius:12px;margin:10px 0}}
.footer{{margin-top:40px;text-align:center;color:#999;font-size:11px}}
</style></head><body>

<h1>UrbanEV Maryland: Deep Simulation Analysis</h1>
<p>298M events | Iteration 5 | 130,837 agents | {len(sessions):,} charging sessions | {total_kwh:,.0f} kWh total energy</p>

<div class="g4">
<div class="sb" style="background:#E91E63"><div class="n">{total_kwh:,.0f}</div><div class="l">Total kWh Charged</div></div>
<div class="sb" style="background:#2196F3"><div class="n">{len(sessions):,}</div><div class="l">Charging Sessions</div></div>
<div class="sb" style="background:#4CAF50"><div class="n">{total_home_kwh:,.0f}</div><div class="l">Home kWh ({round(total_home_kwh/max(total_kwh,1)*100)}%)</div></div>
<div class="sb" style="background:#FF9800"><div class="n">{total_public_kwh:,.0f}</div><div class="l">Public kWh ({round(total_public_kwh/max(total_kwh,1)*100)}%)</div></div>
</div>

<h2>1. Grid Energy Demand Profile (kWh by Hour)</h2>
<div class="c"><canvas id="cGrid"></canvas>
<p style="font-size:12px;color:#888">Stacked area: energy drawn from grid by charger type per hour. Peak demand = infrastructure planning input.</p></div>

<h2>2. Individual Agent SoC Trajectories (24-hour)</h2>
<div class="c"><canvas id="cTraces"></canvas>
<p style="font-size:12px;color:#888">Battery state-of-charge over 24 hours for 6 sample agents. Shows charging events, depletion patterns, and PHEV gas-fallback floors.</p></div>

<h2>3. Charger Utilization Map</h2>
<div class="c">
<p>Top 30 most-used chargers. Circle size = session count. Click for details.</p>
<div id="mapUtil"></div></div>

<h2>4. Charging Infrastructure Gap Map</h2>
<div class="c">
<p>Locations where agents wanted to charge but found NO charger (red dots = unmet demand).</p>
<div id="mapGaps"></div></div>

<h2>5. Charging Session Duration</h2>
<div class="g2">
<div class="c"><h3>Session Duration Distribution (minutes)</h3><canvas id="cDur"></canvas></div>
<div class="c"><h3>Trip Distance Distribution</h3><canvas id="cTrip"></canvas></div>
</div>

<h2>6. Income-Stratified Charging Equity</h2>
<div class="g2">
<div class="c"><h3>Avg Charging Sessions per Agent by Income</h3><canvas id="cIncSess"></canvas></div>
<div class="c"><h3>Home vs Public Charging Share by Income</h3><canvas id="cIncType"></canvas></div>
</div>

<h2>7. BEV vs PHEV Comparison</h2>
<div class="g2">
<div class="c"><h3>Total Sessions</h3><canvas id="cBPsess"></canvas></div>
<div class="c"><h3>Avg Session Duration (min)</h3><canvas id="cBPdur"></canvas></div>
</div>

<h2>8. Top Charger Stations</h2>
<div class="c"><table>
<tr><th>Charger</th><th>Type</th><th>Power</th><th>Plugs</th><th>Sessions</th><th>Hours Used</th><th>Utilization</th></tr>
"""
for cid, u in top_util[:20]:
    html += f"<tr><td>{cid}</td><td>{u['type']}</td><td>{u['power']}kW</td><td>{u['plugs']}</td><td>{u['sessions']}</td><td>{u['hours']:.0f}h</td><td>{u['util']*100:.1f}%</td></tr>\n"

html += f"""</table></div>

<div class="footer">UrbanEV-v2 Maryland | Deep Analysis from 298M events | Iteration 5<br>github.com/Tomal121186621/UrbanEV-MATSim-Maryland</div>

<script>
const C={{b:'#2196F3',g:'#4CAF50',o:'#FF9800',p:'#E91E63',v:'#673AB7',t:'#009688',r:'#F44336',y:'#FFC107'}};

// Grid demand
new Chart(document.getElementById('cGrid'),{{type:'bar',
data:{{labels:{h_labels},datasets:[
{{label:'Home',data:{h_home},backgroundColor:'rgba(76,175,80,0.7)'}},
{{label:'Work',data:{h_work},backgroundColor:'rgba(33,150,243,0.7)'}},
{{label:'Public',data:{h_public},backgroundColor:'rgba(255,152,0,0.7)'}}
]}},options:{{plugins:{{title:{{display:true,text:'24-Hour Grid Energy Demand (kWh)'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,title:{{display:true,text:'kWh'}}}}}}}}
}});

// SoC traces
new Chart(document.getElementById('cTraces'),{{type:'scatter',
data:{{datasets:[{trace_datasets}]}},
options:{{plugins:{{title:{{display:true,text:'Battery SoC Over 24 Hours (% capacity)'}}}},
scales:{{x:{{title:{{display:true,text:'Hour of Day'}},min:0,max:240}},y:{{title:{{display:true,text:'SoC (%)'}},min:0,max:100}}}}}}
}});

// Duration
new Chart(document.getElementById('cDur'),{{type:'bar',
data:{{labels:{dur_labels_hist},datasets:[{{label:'Sessions',data:{dur_home_h},backgroundColor:C.v}}]}},
options:{{plugins:{{title:{{display:true,text:'Duration (minutes)'}}}}}}
}});

// Trip distance
new Chart(document.getElementById('cTrip'),{{type:'bar',
data:{{labels:{td_labels},datasets:[{{label:'Trips',data:{td_counts},backgroundColor:C.t}}]}}
}});

// Income sessions
new Chart(document.getElementById('cIncSess'),{{type:'bar',
data:{{labels:{inc_labels},datasets:[{{label:'Avg Sessions/Agent',data:{inc_sessions},backgroundColor:C.b}}]}}
}});

// Income type split
new Chart(document.getElementById('cIncType'),{{type:'bar',
data:{{labels:{inc_labels},datasets:[
{{label:'Home %',data:{inc_home_pct},backgroundColor:C.g}},
{{label:'Public %',data:{inc_public_pct},backgroundColor:C.o}}
]}},options:{{scales:{{x:{{stacked:true}},y:{{stacked:true}}}}}}
}});

// BEV vs PHEV sessions
new Chart(document.getElementById('cBPsess'),{{type:'bar',
data:{{labels:{bp_labels},datasets:[{{label:'Sessions',data:{bp_sessions},backgroundColor:[C.b,C.p]}}]}}
}});
new Chart(document.getElementById('cBPdur'),{{type:'bar',
data:{{labels:{bp_labels},datasets:[{{label:'Avg Duration (min)',data:{bp_avg_dur},backgroundColor:[C.b,C.p]}}]}}
}});

// Utilization map
var m1=L.map('mapUtil').setView([39.1,-76.7],8);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'OSM'}}).addTo(m1);
{json.dumps(util_map_data)}.forEach(function(m){{
L.circleMarker([m.lat,m.lon],{{radius:Math.min(20,4+m.sessions/10),color:m.type.includes('DCFC')?'#E91E63':'#2196F3',fillOpacity:0.7}}).addTo(m1)
.bindPopup('<b>'+m.id+'</b><br>Type:'+m.type+'<br>Power:'+m.power+'kW<br>Plugs:'+m.plugs+'<br>Sessions:'+m.sessions+'<br>Hours:'+m.hours+'<br>Util:'+m.util+'%');
}});

// Gap map
var m2=L.map('mapGaps').setView([39.1,-76.7],8);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'OSM'}}).addTo(m2);
{json.dumps(gap_locs)}.forEach(function(m){{
L.circleMarker([m.lat,m.lon],{{radius:4,color:'#F44336',fillColor:'#F44336',fillOpacity:0.6}}).addTo(m2);
}});
</script></body></html>"""

with open(f"{OUT}/deep_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

# Save CSVs
with open(f"{OUT}/grid_demand_hourly.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["hour", "home_kwh", "work_kwh", "public_kwh", "total_kwh"])
    for h in range(24):
        w.writerow([h, round(hourly_home_grid.get(h,0),1), round(hourly_work_grid.get(h,0),1),
                    round(hourly_public_grid.get(h,0),1),
                    round(hourly_home_grid.get(h,0)+hourly_work_grid.get(h,0)+hourly_public_grid.get(h,0),1)])

with open(f"{OUT}/charger_utilization.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["charger_id","type","power_kw","plugs","sessions","hours_used","utilization_pct","x","y"])
    for cid, u in sorted(charger_util.items(), key=lambda x:-x[1]['sessions'])[:100]:
        w.writerow([cid, u['type'], u['power'], u['plugs'], u['sessions'],
                    round(u['hours'],1), round(u['util']*100,1), u['x'], u['y']])

with open(f"{OUT}/income_charging_equity.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["income_bracket","income_midpoint","agents","total_sessions","home_sessions","work_sessions","public_sessions","avg_sessions_per_agent"])
    for inc in sorted(income_charging.keys()):
        if inc > 9: continue
        g = income_charging[inc]
        w.writerow([inc, income_mp.get(inc,0), g['agents'], g['sessions'], g['home'], g['work'], g['public'],
                    round(g['sessions']/max(g['agents'],1),2)])

print(f"\n{'='*70}")
print(f"Deep analysis complete!")
print(f"  Dashboard: {OUT}/deep_dashboard.html")
print(f"  CSVs: grid_demand_hourly.csv, charger_utilization.csv, income_charging_equity.csv")
print(f"{'='*70}")
