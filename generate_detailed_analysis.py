#!/usr/bin/env python3
"""
Detailed post-analysis: en-route behavior, workplace charging, queues,
corridors, and spatial mapping.
"""
import gzip
import csv
import os
import json
import re
import math
from collections import defaultdict

EVENTS_FILE = "output/maryland_ev_enhanced/ITERS/it.5/maryland_ev_v2.5.events.xml.gz"
LOG_FILE = "full_simulation.log"
CHARGERS_FILE = "Input Files/chargers.xml"
SUMMARY_FILE = "Input Files/ev_population_summary.csv"
OUTPUT_DIR = "analysis_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_attr(line, attr):
    key = f'{attr}="'
    s = line.find(key)
    if s < 0: return None
    s += len(key)
    e = line.find('"', s)
    return line[s:e] if e > s else None

# EPSG:26985 to WGS84 approximate conversion for mapping
# Maryland State Plane NAD83 -> lat/lon (rough linear approx for MD region)
def sp_to_latlon(x, y):
    # Approximate center: x=400000 y=150000 -> lat=39.0 lon=-76.7
    lon = -76.7 + (x - 400000) / 85000
    lat = 39.0 + (y - 150000) / 111000
    return round(lat, 5), round(lon, 5)

print("=" * 70)
print("UrbanEV Detailed Analysis: En-Route, Workplace, Corridors")
print("=" * 70)

# ══════════════════════════════════════════════════════════════════════
# 1. Parse Charger Locations
# ══════════════════════════════════════════════════════════════════════
print("\n1. Parsing charger locations...")
charger_coords = {}  # id -> (x, y, type, power, plugs)
with open(CHARGERS_FILE, 'r') as f:
    for line in f:
        if '<charger ' in line:
            cid = get_attr(line, 'id')
            ct = get_attr(line, 'type')
            x = float(get_attr(line, 'x') or '0')
            y = float(get_attr(line, 'y') or '0')
            power = float(get_attr(line, 'plug_power') or '0')
            plugs = int(get_attr(line, 'plug_count') or '1')
            charger_coords[cid] = (x, y, ct, power, plugs)
print(f"  {len(charger_coords)} chargers loaded")

# ══════════════════════════════════════════════════════════════════════
# 2. Parse En-Route Insertions from Log
# ══════════════════════════════════════════════════════════════════════
print("\n2. Parsing en-route insertions from log...")
enroute_data = []
enroute_charger_usage = defaultdict(int)
enroute_risk = defaultdict(int)
enroute_type = defaultdict(int)  # DCFC vs L2
enroute_durations = []
enroute_distances = []
enroute_energies = []
enroute_powers = []

with open(LOG_FILE, 'r', errors='ignore') as f:
    for line in f:
        if 'InsertEnRoute: inserted' in line:
            charger_id = re.search(r'at charger (\S+)', line)
            risk = re.search(r'riskAttitude=(\w+)', line)
            power = re.search(r'power=([0-9.]+)', line)
            ctype = 'DCFC' if 'DCFC' in line else 'L2'

            if charger_id:
                cid = charger_id.group(1)
                enroute_charger_usage[cid] += 1
            if risk:
                enroute_risk[risk.group(1)] += 1
            enroute_type[ctype] += 1
            if power:
                enroute_powers.append(float(power.group(1)))

        elif 'InsertEnRoute: dynamic' in line:
            dur = re.search(r'duration=(\d+)s', line)
            dist = re.search(r'remainDist=(\d+)m', line)
            energy = re.search(r'energyNeeded=([0-9.]+)kWh', line)

            if dur: enroute_durations.append(int(dur.group(1)))
            if dist: enroute_distances.append(int(dist.group(1)))
            if energy: enroute_energies.append(float(energy.group(1)))

total_enroute = sum(enroute_type.values())
print(f"  {total_enroute:,} en-route insertions")
print(f"  DCFC: {enroute_type.get('DCFC', 0):,} | L2: {enroute_type.get('L2', 0):,}")

# ══════════════════════════════════════════════════════════════════════
# 3. Parse Workplace Charging from Log
# ══════════════════════════════════════════════════════════════════════
print("\n3. Parsing workplace charging...")
workplace_full = 0
workplace_chargers = {}  # charger_id -> (x, y, plugs)
with open(LOG_FILE, 'r', errors='ignore') as f:
    for line in f:
        if 'charger FULL' in line and 'workplace_' in line:
            workplace_full += 1
        if 'Workplace charging: created' in line:
            m = re.search(r'created (\d+) shared.*from (\d+) EV', line)
            if m:
                print(f"  {m.group(1)} pools from {m.group(2)} workers")

# Find workplace chargers in charger_coords
for cid, (x, y, ct, power, plugs) in charger_coords.items():
    if 'workplace_' in cid:
        workplace_chargers[cid] = (x, y, plugs)
print(f"  {len(workplace_chargers)} workplace charger pools")
print(f"  {workplace_full:,} charger-full events")

# ══════════════════════════════════════════════════════════════════════
# 4. Parse Events for Queue/Wait/Detour Analysis
# ══════════════════════════════════════════════════════════════════════
print("\n4. Parsing events for charging session details...")
charging_sessions = []  # (personId, chargerType, energyKwh, power, walkDist)
charger_session_count = defaultdict(int)
charger_session_kwh = defaultdict(float)
agent_home_xy = {}

# Load agent home coords
with open(SUMMARY_FILE) as f:
    for row in csv.DictReader(f):
        pid = row['person_id']
        agent_home_xy[pid] = (float(row.get('home_x', 0)), float(row.get('home_y', 0)))

with gzip.open(EVENTS_FILE, 'rt') as f:
    for line in f:
        if 'type="scoring"' not in line: continue
        if 'costOnly="true"' not in line: continue

        energy = get_attr(line, 'energyChargedKWh')
        ct = get_attr(line, 'chargerType')
        power = get_attr(line, 'chargerPowerKw')
        person = get_attr(line, 'person')
        time_str = get_attr(line, 'time')

        if not energy or not ct: continue
        e = float(energy)
        if e <= 0: continue

        p = float(power) if power else 0
        hour = int(float(time_str) / 3600) % 24 if time_str else 0

        charging_sessions.append({
            'person': person, 'type': ct, 'kwh': e, 'power': p, 'hour': hour
        })

print(f"  {len(charging_sessions):,} charging sessions parsed")

# ══════════════════════════════════════════════════════════════════════
# 5. Corridor Analysis
# ══════════════════════════════════════════════════════════════════════
print("\n5. Building corridor analysis...")

# Define major MD corridors by bounding boxes (EPSG:26985)
corridors = {
    "I-95 Baltimore-DC": {"x_min": 380000, "x_max": 420000, "y_min": 130000, "y_max": 200000},
    "I-270 Frederick-DC": {"x_min": 350000, "x_max": 400000, "y_min": 147000, "y_max": 220000},
    "I-70 Baltimore-Frederick": {"x_min": 320000, "x_max": 420000, "y_min": 200000, "y_max": 225000},
    "US-50 Annapolis-Ocean City": {"x_min": 420000, "x_max": 530000, "y_min": 80000, "y_max": 160000},
    "I-83 Baltimore-PA": {"x_min": 410000, "x_max": 440000, "y_min": 190000, "y_max": 230000},
    "I-95 Baltimore-NE": {"x_min": 420000, "x_max": 480000, "y_min": 190000, "y_max": 230000},
}

corridor_chargers = defaultdict(list)  # corridor -> [(cid, x, y, type, usage)]
corridor_enroute = defaultdict(int)

for cid, (x, y, ct, power, plugs) in charger_coords.items():
    for corr_name, bounds in corridors.items():
        if bounds["x_min"] <= x <= bounds["x_max"] and bounds["y_min"] <= y <= bounds["y_max"]:
            usage = enroute_charger_usage.get(cid, 0) + charger_session_count.get(cid, 0)
            corridor_chargers[corr_name].append((cid, x, y, ct, usage, power, plugs))

for cid, usage in enroute_charger_usage.items():
    if cid in charger_coords:
        x, y = charger_coords[cid][0], charger_coords[cid][1]
        for corr_name, bounds in corridors.items():
            if bounds["x_min"] <= x <= bounds["x_max"] and bounds["y_min"] <= y <= bounds["y_max"]:
                corridor_enroute[corr_name] += usage

# ══════════════════════════════════════════════════════════════════════
# 6. Generate Detailed HTML Dashboard
# ══════════════════════════════════════════════════════════════════════
print("\n6. Generating detailed dashboard...")

# Prepare en-route chart data
dur_labels = json.dumps(["5min", "5-10min", "10-15min", "15-20min", "20-30min", "30-45min", ">45min"])
dur_counts = json.dumps([
    sum(1 for d in enroute_durations if d <= 300),
    sum(1 for d in enroute_durations if 300 < d <= 600),
    sum(1 for d in enroute_durations if 600 < d <= 900),
    sum(1 for d in enroute_durations if 900 < d <= 1200),
    sum(1 for d in enroute_durations if 1200 < d <= 1800),
    sum(1 for d in enroute_durations if 1800 < d <= 2700),
    sum(1 for d in enroute_durations if d > 2700),
])

dist_labels = json.dumps(["<5km", "5-20km", "20-50km", "50-100km", ">100km"])
dist_counts = json.dumps([
    sum(1 for d in enroute_distances if d < 5000),
    sum(1 for d in enroute_distances if 5000 <= d < 20000),
    sum(1 for d in enroute_distances if 20000 <= d < 50000),
    sum(1 for d in enroute_distances if 50000 <= d < 100000),
    sum(1 for d in enroute_distances if d >= 100000),
])

energy_labels = json.dumps(["<2kWh", "2-5kWh", "5-10kWh", "10-20kWh", ">20kWh"])
energy_counts = json.dumps([
    sum(1 for e in enroute_energies if e < 2),
    sum(1 for e in enroute_energies if 2 <= e < 5),
    sum(1 for e in enroute_energies if 5 <= e < 10),
    sum(1 for e in enroute_energies if 10 <= e < 20),
    sum(1 for e in enroute_energies if e >= 20),
])

risk_labels = json.dumps(list(enroute_risk.keys()))
risk_counts = json.dumps(list(enroute_risk.values()))

type_labels = json.dumps(list(enroute_type.keys()))
type_counts = json.dumps(list(enroute_type.values()))

# Power distribution
power_labels = json.dumps(["7.2kW (L2)", "50kW", "62.5kW", "100kW", "150kW"])
power_counts = json.dumps([
    sum(1 for p in enroute_powers if p < 10),
    sum(1 for p in enroute_powers if 45 <= p < 55),
    sum(1 for p in enroute_powers if 55 <= p < 80),
    sum(1 for p in enroute_powers if 80 <= p < 120),
    sum(1 for p in enroute_powers if p >= 120),
])

# Map data: top en-route chargers
top_enroute = sorted(enroute_charger_usage.items(), key=lambda x: -x[1])[:50]
map_markers = []
for cid, usage in top_enroute:
    if cid in charger_coords:
        x, y, ct, power, plugs = charger_coords[cid]
        lat, lon = sp_to_latlon(x, y)
        color = 'red' if ct == 'DCFC' or ct == 'DCFC_TESLA' else 'blue'
        map_markers.append({
            'lat': lat, 'lon': lon, 'id': cid, 'type': ct,
            'power': power, 'plugs': plugs, 'usage': usage, 'color': color
        })

# All charger map data
all_charger_markers = []
for cid, (x, y, ct, power, plugs) in charger_coords.items():
    if 'workplace_' in cid or '_home' in cid: continue  # skip private
    lat, lon = sp_to_latlon(x, y)
    color = '#e91e63' if 'DCFC' in ct else '#2196F3'
    all_charger_markers.append({
        'lat': lat, 'lon': lon, 'id': cid, 'type': ct,
        'power': power, 'plugs': plugs, 'color': color
    })

# Workplace charger map data
wp_markers = []
for cid, (x, y, plugs) in workplace_chargers.items():
    lat, lon = sp_to_latlon(x, y)
    wp_markers.append({'lat': lat, 'lon': lon, 'id': cid, 'plugs': plugs})

# Corridor summary
corridor_rows = ""
for corr_name in sorted(corridors.keys()):
    chargers_list = corridor_chargers.get(corr_name, [])
    n_dcfc = sum(1 for c in chargers_list if 'DCFC' in c[3])
    n_l2 = sum(1 for c in chargers_list if c[3] == 'L2')
    n_enroute = corridor_enroute.get(corr_name, 0)
    total_plugs = sum(c[6] for c in chargers_list)
    corridor_rows += f"<tr><td>{corr_name}</td><td>{len(chargers_list)}</td><td>{n_dcfc}</td><td>{n_l2}</td><td>{total_plugs}</td><td>{n_enroute}</td></tr>\n"

# Charging by hour for workplace
wp_sessions_by_hour = defaultdict(int)
home_sessions_by_hour = defaultdict(int)
public_sessions_by_hour = defaultdict(int)
for s in charging_sessions:
    if s['type'] == 'work':
        wp_sessions_by_hour[s['hour']] += 1
    elif s['type'] == 'home':
        home_sessions_by_hour[s['hour']] += 1
    elif s['type'] == 'public':
        public_sessions_by_hour[s['hour']] += 1

hourly_labels = json.dumps(list(range(24)))
hourly_home = json.dumps([home_sessions_by_hour.get(h, 0) for h in range(24)])
hourly_work = json.dumps([wp_sessions_by_hour.get(h, 0) for h in range(24)])
hourly_public = json.dumps([public_sessions_by_hour.get(h, 0) for h in range(24)])

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UrbanEV Maryland - Detailed Analysis Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
h1 {{ color: #1a1a2e; border-bottom: 3px solid #673AB7; padding-bottom: 10px; }}
h2 {{ color: #673AB7; margin-top: 40px; border-left: 4px solid #673AB7; padding-left: 12px; }}
h3 {{ color: #2196F3; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
.grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin: 20px 0; }}
.card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.card h3 {{ margin-top: 0; }}
.metric {{ display: inline-block; background: #ede7f6; padding: 8px 16px; border-radius: 8px; margin: 4px; font-weight: bold; }}
.metric.green {{ background: #e8f5e9; }}
.metric.red {{ background: #fce4ec; }}
.metric.blue {{ background: #e8f4fd; }}
canvas {{ max-height: 320px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
th {{ background: #673AB7; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
td:first-child {{ text-align: left; }}
#map, #mapAll, #mapWorkplace {{ height: 450px; border-radius: 12px; margin: 10px 0; }}
.footer {{ margin-top: 40px; text-align: center; color: #888; font-size: 12px; }}
.stat-box {{ background: #673AB7; color: white; padding: 15px 20px; border-radius: 12px; text-align: center; }}
.stat-box .number {{ font-size: 28px; font-weight: bold; }}
.stat-box .label {{ font-size: 12px; opacity: 0.8; }}
</style>
</head>
<body>

<h1>UrbanEV-v2 Maryland: Detailed Analysis Dashboard</h1>
<p>En-Route Charging | Workplace Competition | Corridors | Spatial Analysis | Iteration 5</p>

<div class="grid3">
<div class="stat-box"><div class="number">{total_enroute:,}</div><div class="label">En-Route Insertions</div></div>
<div class="stat-box" style="background:#2196F3"><div class="number">{len(charging_sessions):,}</div><div class="label">Total Charging Sessions</div></div>
<div class="stat-box" style="background:#4CAF50"><div class="number">{workplace_full:,}</div><div class="label">Workplace Queue Events</div></div>
</div>

<!-- ════════════════════════════════════════════ -->
<h2>En-Route Charging Behavior</h2>

<div class="grid">
<div class="card">
<h3>DCFC vs L2 Selection</h3>
<canvas id="chartEnrouteType"></canvas>
</div>
<div class="card">
<h3>Risk Attitude Distribution</h3>
<canvas id="chartRisk"></canvas>
</div>
</div>

<div class="grid">
<div class="card">
<h3>Charge Duration Distribution</h3>
<canvas id="chartDuration"></canvas>
</div>
<div class="card">
<h3>Remaining Distance When Stopping</h3>
<canvas id="chartRemainDist"></canvas>
</div>
</div>

<div class="grid">
<div class="card">
<h3>Energy Needed at En-Route Stop</h3>
<canvas id="chartEnrouteEnergy"></canvas>
</div>
<div class="card">
<h3>Charger Power Used (kW)</h3>
<canvas id="chartPower"></canvas>
</div>
</div>

<!-- ════════════════════════════════════════════ -->
<h2>En-Route Charger Hotspot Map</h2>
<div class="card">
<p>Top 50 most-used en-route chargers. Red = DCFC, Blue = L2. Circle size = usage count.</p>
<div id="map"></div>
</div>

<!-- ════════════════════════════════════════════ -->
<h2>All Public Chargers Map</h2>
<div class="card">
<p>All 1,958 public chargers in Maryland + DC. Pink = DCFC/Tesla, Blue = L2.</p>
<div id="mapAll"></div>
</div>

<!-- ════════════════════════════════════════════ -->
<h2>Workplace Charging</h2>

<div class="grid">
<div class="card">
<h3>Charging Sessions by Hour (by Type)</h3>
<canvas id="chartHourlyByType"></canvas>
</div>
<div class="card">
<h3>Workplace Charger Locations</h3>
<div id="mapWorkplace" style="height:320px"></div>
</div>
</div>

<div class="card">
<h3>Workplace Charging Stats</h3>
<span class="metric">{len(workplace_chargers)} shared pools</span>
<span class="metric blue">1:5 worker-to-plug ratio</span>
<span class="metric red">{workplace_full:,} queue-full events</span>
<span class="metric green">{len([s for s in charging_sessions if s['type']=='work']):,} work sessions in iter 5</span>
</div>

<!-- ════════════════════════════════════════════ -->
<h2>Corridor Analysis</h2>

<div class="card">
<h3>Major Maryland Corridors — Charger Coverage</h3>
<table>
<tr><th>Corridor</th><th>Total Chargers</th><th>DCFC</th><th>L2</th><th>Total Plugs</th><th>En-Route Usage</th></tr>
{corridor_rows}
</table>
</div>

<!-- ════════════════════════════════════════════ -->
<h2>Top En-Route Charger Stations</h2>
<div class="card">
<table>
<tr><th>Charger ID</th><th>Type</th><th>Power (kW)</th><th>Plugs</th><th>En-Route Usage</th></tr>
"""

for cid, usage in top_enroute[:20]:
    if cid in charger_coords:
        x, y, ct, power, plugs = charger_coords[cid]
        html += f"<tr><td>{cid}</td><td>{ct}</td><td>{power}</td><td>{plugs}</td><td>{usage}</td></tr>\n"

html += f"""</table>
</div>

<div class="footer">
UrbanEV-v2 Maryland | Iteration 5 Analysis | {total_enroute:,} en-route insertions | {len(charging_sessions):,} charging sessions<br>
github.com/Tomal121186621/UrbanEV-MATSim-Maryland
</div>

<script>
const C = {{
    blue: '#2196F3', green: '#4CAF50', orange: '#FF9800',
    pink: '#E91E63', purple: '#673AB7', teal: '#009688',
    red: '#F44336', yellow: '#FFC107'
}};

// En-route type
new Chart(document.getElementById('chartEnrouteType'), {{
    type: 'doughnut',
    data: {{ labels: {type_labels}, datasets: [{{ data: {type_counts}, backgroundColor: [C.red, C.blue] }}] }}
}});

// Risk attitude
new Chart(document.getElementById('chartRisk'), {{
    type: 'pie',
    data: {{ labels: {risk_labels}, datasets: [{{ data: {risk_counts}, backgroundColor: [C.purple, C.orange, C.teal] }}] }}
}});

// Duration
new Chart(document.getElementById('chartDuration'), {{
    type: 'bar',
    data: {{ labels: {dur_labels}, datasets: [{{ label: 'Insertions', data: {dur_counts}, backgroundColor: C.purple }}] }},
    options: {{ plugins: {{ title: {{ display: true, text: 'How long do agents charge en-route?' }} }} }}
}});

// Remaining distance
new Chart(document.getElementById('chartRemainDist'), {{
    type: 'bar',
    data: {{ labels: {dist_labels}, datasets: [{{ label: 'Insertions', data: {dist_counts}, backgroundColor: C.teal }}] }},
    options: {{ plugins: {{ title: {{ display: true, text: 'Distance remaining when en-route stop inserted' }} }} }}
}});

// Energy needed
new Chart(document.getElementById('chartEnrouteEnergy'), {{
    type: 'bar',
    data: {{ labels: {energy_labels}, datasets: [{{ label: 'Insertions', data: {energy_counts}, backgroundColor: C.orange }}] }}
}});

// Power
new Chart(document.getElementById('chartPower'), {{
    type: 'bar',
    data: {{ labels: {power_labels}, datasets: [{{ label: 'Insertions', data: {power_counts}, backgroundColor: [C.blue, C.green, C.orange, C.red, C.pink] }}] }}
}});

// Hourly by type
new Chart(document.getElementById('chartHourlyByType'), {{
    type: 'bar',
    data: {{
        labels: {hourly_labels},
        datasets: [
            {{ label: 'Home', data: {hourly_home}, backgroundColor: C.green }},
            {{ label: 'Work', data: {hourly_work}, backgroundColor: C.blue }},
            {{ label: 'Public', data: {hourly_public}, backgroundColor: C.orange }},
        ]
    }},
    options: {{ plugins: {{ title: {{ display: true, text: '24-Hour Charging Profile by Type' }} }}, scales: {{ x: {{ stacked: true }}, y: {{ stacked: true }} }} }}
}});

// En-route hotspot map
var map = L.map('map').setView([39.1, -76.7], 8);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: 'OpenStreetMap'
}}).addTo(map);

var enrouteMarkers = {json.dumps(map_markers)};
enrouteMarkers.forEach(function(m) {{
    L.circleMarker([m.lat, m.lon], {{
        radius: Math.min(20, 4 + m.usage / 5),
        color: m.color, fillColor: m.color, fillOpacity: 0.7
    }}).addTo(map).bindPopup(
        '<b>' + m.id + '</b><br>Type: ' + m.type + '<br>Power: ' + m.power + ' kW<br>Plugs: ' + m.plugs + '<br>En-route usage: ' + m.usage
    );
}});

// All chargers map
var mapAll = L.map('mapAll').setView([39.1, -76.7], 8);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: 'OpenStreetMap'
}}).addTo(mapAll);

var allMarkers = {json.dumps(all_charger_markers)};
allMarkers.forEach(function(m) {{
    L.circleMarker([m.lat, m.lon], {{
        radius: m.type.includes('DCFC') ? 6 : 3,
        color: m.color, fillColor: m.color, fillOpacity: 0.6
    }}).addTo(mapAll).bindPopup(
        '<b>' + m.id + '</b><br>Type: ' + m.type + '<br>Power: ' + m.power + ' kW<br>Plugs: ' + m.plugs
    );
}});

// Workplace map
var mapWP = L.map('mapWorkplace').setView([39.1, -76.7], 9);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: 'OpenStreetMap'
}}).addTo(mapWP);

var wpMarkers = {json.dumps(wp_markers)};
wpMarkers.forEach(function(m) {{
    L.circleMarker([m.lat, m.lon], {{
        radius: Math.min(15, 3 + m.plugs / 2),
        color: '#4CAF50', fillColor: '#4CAF50', fillOpacity: 0.6
    }}).addTo(mapWP).bindPopup(
        '<b>' + m.id + '</b><br>Plugs: ' + m.plugs
    );
}});
</script>
</body>
</html>
"""

with open(f"{OUTPUT_DIR}/detailed_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n{'='*70}")
print(f"Detailed analysis complete!")
print(f"  Dashboard: {OUTPUT_DIR}/detailed_dashboard.html")
print(f"  Open in browser for interactive maps and charts")
print(f"{'='*70}")
