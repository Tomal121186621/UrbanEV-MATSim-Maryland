#!/usr/bin/env python3
"""Generate a comprehensive pipeline diagram for the UrbanEV simulation."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(1, 1, figsize=(26, 34))
ax.set_xlim(0, 26)
ax.set_ylim(0, 34)
ax.axis('off')
fig.patch.set_facecolor('#f8f9fa')

# Colors
C_INPUT = '#e8f4fd'; C_IB = '#2196F3'
C_PROC = '#fff3e0'; C_PB = '#FF9800'
C_CHG = '#fce4ec'; C_CB = '#e91e63'
C_OUT = '#e8f5e9'; C_OB = '#4CAF50'
C_SIM = '#ede7f6'; C_SB = '#673AB7'

def box(x, y, w, h, text, fc, ec, fs=8, bold=False):
    p = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.15',
                        facecolor=fc, edgecolor=ec, linewidth=2, alpha=0.92)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fs,
            fontweight='bold' if bold else 'normal', family='sans-serif', linespacing=1.3)

def header(y, text, color='#37474f'):
    ax.text(13, y, text, ha='center', va='center', fontsize=13, fontweight='bold',
            color='white', bbox=dict(boxstyle='round,pad=0.4', facecolor=color, edgecolor=color))

def arrow(x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color='#455a64', lw=2))

# ── TITLE ──
ax.text(13, 33.3, 'UrbanEV-v2: Maryland + DC EV Charging Simulation',
        ha='center', fontsize=20, fontweight='bold', color='#1a1a2e')
ax.text(13, 32.7, '362,374 EV Agents (255K BEV + 107K PHEV)  |  9.8M Link Network  |  EPSG:26985  |  MATSim 12',
        ha='center', fontsize=11, color='#555')

# ══════════════════════════════════════════════════════════════
# 1. RAW INPUTS
# ══════════════════════════════════════════════════════════════
header(32.0, '1. RAW INPUTS')

box(0.3, 30.3, 6, 1.3,
    'Synthetic Population CSV\nsynthetic_bmc_v3_with_coords.csv\n4.93 GB  |  19.9M rows  |  6.1M persons',
    C_INPUT, C_IB)

box(6.8, 30.3, 4.5, 1.3,
    'AFDC Charger Data\nMD + DC (Mar 2026)\n1,958 chargers',
    C_INPUT, C_IB)

box(11.8, 30.3, 5, 1.3,
    'OSM Road Network\nmaryland-dc-ev-network.xml.gz\n284 MB  |  4.9M nodes  |  9.8M links',
    C_INPUT, C_IB)

box(17.3, 30.3, 4, 1.3,
    'Through Stations\n14 highway boundary\ncrossing points',
    C_INPUT, C_IB)

box(21.8, 30.3, 3.8, 1.3,
    'RTS Codebook\nData dictionary\nAge/income/mode codes',
    C_INPUT, C_IB)

# ══════════════════════════════════════════════════════════════
# 2. CONVERSION
# ══════════════════════════════════════════════════════════════
header(29.3, '2. DATA CONVERSION  (pink = our changes)')

box(0.3, 27.2, 8, 1.7,
    'convert_synpop_v3_to_matsim.py  [NEW SCRIPT]\n'
    'Streams 5GB CSV -> MATSim XMLs (EV agents only)\n'
    'Constructs person_id = household_id + person_slot\n'
    'Maps age_group (13 RTS codes) -> representative ages\n'
    'Derives: homeCharger, betaMoney, VoT, riskAttitude',
    C_CHG, C_CB, 7.5, True)

box(8.8, 27.2, 7, 1.7,
    'KEY CHANGES vs Original Script\n'
    'has_ev=1  (was assigned_ev=1)\n'
    'ev1_make / ev1_model / ev1_type  (new cols)\n'
    'PHEV support: 17 new models + battery specs\n'
    'j1_benefits_ev_charging -> work charger\n'
    'Network bbox check for external trip snapping',
    C_CHG, C_CB, 7.5)

box(16.3, 27.2, 9.3, 1.7,
    'convert_afdc_to_chargers_xml.py  (unchanged)\n'
    'AFDC CSV -> chargers.xml + metadata\n'
    'WGS84 -> EPSG:26985 coordinate transform\n'
    '1,607 L2 + 283 DCFC + 68 DCFC_TESLA',
    C_PROC, C_PB, 7.5)

# Arrows
arrow(3.3, 30.3, 4.3, 28.9)
arrow(9.0, 30.3, 8.3, 28.9)
arrow(19.3, 30.3, 19.3, 28.9)

# ══════════════════════════════════════════════════════════════
# 3. GENERATED INPUTS
# ══════════════════════════════════════════════════════════════
header(26.2, '3. GENERATED MATSim INPUT FILES')

box(0.3, 24.3, 4.8, 1.5,
    'plans_maryland_ev\n.xml.gz\n362,374 agents\n1,183,157 trips\n28.3 MB',
    C_OUT, C_OB)

box(5.5, 24.3, 4.5, 1.5,
    'electric_vehicles.xml\n362,374 EVs\n33 vehicle types\nBEV + PHEV\n46.4 MB',
    C_OUT, C_OB)

box(10.4, 24.3, 5, 1.5,
    'vehicletypes.xml  [CHANGED]\n33 EV types + default "car"\nPHEV consumption rates\n"car" type fixes\nPrepareForSim NPE',
    C_CHG, C_CB)

box(15.8, 24.3, 5, 1.5,
    'urbanev_vehicletypes.xml\n[CHANGED - Sweden fmt]\n49 types (was 35)\n+14 PHEV types\n+2 generic fallbacks',
    C_CHG, C_CB)

box(21.2, 24.3, 4.5, 1.5,
    'chargers.xml\n1,958 chargers\nL2 / DCFC /\nDCFC_TESLA\nEPSG:26985',
    C_OUT, C_OB)

arrow(4.3, 27.2, 2.7, 25.8)
arrow(4.3, 27.2, 7.75, 25.8)
arrow(4.3, 27.2, 12.9, 25.8)
arrow(4.3, 27.2, 18.3, 25.8)
arrow(21.0, 27.2, 23.4, 25.8)

# ══════════════════════════════════════════════════════════════
# 4. CONFIG & JAVA CHANGES
# ══════════════════════════════════════════════════════════════
header(23.3, '4. CONFIGURATION & CODE CHANGES  (all pink = our fixes)')

box(0.3, 20.8, 8, 2.0,
    'config.xml  CHANGES\n\n'
    'routingAlgorithm: Dijkstra -> FastAStarLandmarks\n'
    'global.numberOfThreads: 0 (=1!) -> 14\n'
    'flowCapacityFactor: 0.02 -> 0.06\n'
    'storageCapacityFactor: 0.06 -> 0.18\n'
    'stuckTime: 300s -> 900s\n'
    'endTime: 168h -> 240h (10-day window)',
    C_CHG, C_CB, 8, True)

box(8.8, 20.8, 8, 2.0,
    'GotEVMain.java  CHANGES\n\n'
    'REMOVED forced single-thread override:\n'
    '  config.parallelEventHandling()\n'
    '    .setNumberOfThreads(1)  // KILLED PERF!\n\n'
    'Now uses config value (14 threads)\n'
    'Enables parallel routing + event handling',
    C_CHG, C_CB, 8, True)

box(17.3, 20.8, 8.3, 2.0,
    'JVM Tuning  (Ryzen 7 2700X, 128GB RAM)\n\n'
    '-Xmx120g  -Xms64g  (max RAM)\n'
    '-XX:+AlwaysPreTouch (no page faults)\n'
    '-XX:ParallelGCThreads=14\n'
    'QSim: 14 threads\n'
    '--add-opens for JDK 17 + Guice CGLIB',
    C_PROC, C_PB, 8)

# ══════════════════════════════════════════════════════════════
# 5. SIMULATION ENGINE
# ══════════════════════════════════════════════════════════════
header(20.0, '5. UrbanEV-v2 SIMULATION ENGINE (MATSim Co-evolutionary Loop)')

box(0.3, 17.2, 5.5, 2.3,
    'MATSim Core Loop\n(10 test / 60 production iters)\n\n'
    '1. Route Plans (FastA* 14 threads)\n'
    '2. QSim Mobsim (14 threads)\n'
    '3. Score Plans\n'
    '4. Replan (strategies)\n'
    '5. Select Best Plan\n'
    '6. Repeat',
    C_SIM, C_SB, 8)

box(6.3, 17.2, 6, 2.3,
    'UrbanEV Modules\n\n'
    'EvModule\n'
    '  -> ChargingModule\n'
    '  -> DischargingModule\n'
    '  -> ElectricFleetModule\n'
    'MobsimScopeEventHandling\n'
    '  -> Home/Work charger gen\n'
    '  -> Range anxiety monitor\n'
    'VehicleChargingHandler\n'
    'SmartChargingEngine',
    C_SIM, C_SB, 7.5)

box(12.8, 17.2, 6, 2.3,
    'Strategy Modules\n\n'
    'nonCriticalSOC subpopulation:\n'
    '  SelectExpBeta: 0.6\n'
    '  ChangeChargingBehaviour: 0.2\n'
    '  InsertEnRouteCharging: 0.2\n\n'
    'criticalSOC subpopulation:\n'
    '  ChangeChargingBehaviour: 0.4\n'
    '  InsertEnRouteCharging: 0.6',
    C_SIM, C_SB, 7.5)

box(19.3, 17.2, 6.3, 2.3,
    'Scoring (Decision Drivers)\n\n'
    'rangeAnxietyUtility: -6\n'
    'emptyBatteryUtility: -15\n'
    'walkingUtility: -1\n'
    'homeChargingUtility: +1\n'
    'socDifferenceUtility: -4\n\n'
    'Pricing: Home $0.13, L2 $0.25,\n'
    '         DCFC $0.48 /kWh',
    C_SIM, C_SB, 7.5)

arrow(4.3, 20.8, 3.0, 19.5)
arrow(12.8, 20.8, 9.3, 19.5)
arrow(21.4, 20.8, 22.4, 19.5)

# ══════════════════════════════════════════════════════════════
# 6. AGENT PROFILE
# ══════════════════════════════════════════════════════════════
header(16.4, '6. EV AGENT POPULATION PROFILE')

box(0.3, 14.3, 8, 1.6,
    '362,374 EV Agents\n'
    'BEV: 255,235 (70.4%)  |  PHEV: 107,139 (29.6%)\n'
    'Top: Model Y 62K, Model 3 36K, BEV(generic) 30K\n'
    'Tesla: 134K (37%)  |  Other makes: 228K (63%)',
    C_OUT, C_OB)

box(8.8, 14.3, 8, 1.6,
    'Home Charging Distribution\n'
    'L2 (7.2 kW): 232,214 (64.1%)\n'
    'L1 (1.4 kW): 76,706 (21.2%)\n'
    'No charger: 53,454 (14.7%)\n'
    'Derived from: dwelling + ownership + income',
    C_OUT, C_OB)

box(17.3, 14.3, 8.3, 1.6,
    'Heterogeneous Attributes (per-agent)\n'
    'betaMoney: f(income)  [-50 to -1.5]\n'
    'valueOfTime: f(income, employment)\n'
    'rangeAnxietyThreshold: f(income, age)  [0.10-0.40]\n'
    'riskAttitude: neutral / moderate / averse',
    C_OUT, C_OB)

# ══════════════════════════════════════════════════════════════
# 7. PERFORMANCE
# ══════════════════════════════════════════════════════════════
header(13.5, '7. PERFORMANCE BOTTLENECKS & FIXES')

box(0.3, 11.3, 12.5, 1.7,
    'BEFORE (original config)\n\n'
    'Routing: Dijkstra + 1 thread on 9.8M links = ~210 HOURS\n'
    'Event handling: forced to 1 thread (Java code bug)\n'
    'PrepareForSim: ~6.5 sec/person (single-threaded)\n'
    'Stuck agents: 75% removed (stuckTime=300s, storageCapFactor=0.06)',
    C_CHG, C_CB, 8)

box(13.3, 11.3, 12.3, 1.7,
    'AFTER (our fixes)\n\n'
    'Routing: FastAStarLandmarks + 14 threads = ~2 HOURS  (100x faster)\n'
    'Event handling: 14 threads (config-driven)\n'
    'PrepareForSim: ~0.17 sec/person (14 threads, 38x faster)\n'
    'Stuck agents: expected ~15% (stuckTime=900s, storageCapFactor=0.18)',
    C_OUT, C_OB, 8)

# ══════════════════════════════════════════════════════════════
# 8. OUTPUTS
# ══════════════════════════════════════════════════════════════
header(10.5, '8. SIMULATION OUTPUTS & POST-ANALYSIS')

box(0.3, 8.3, 6.2, 1.8,
    'Per-Iteration Files\n\n'
    'events.xml.gz (~156 MB)\n'
    'plans.xml.gz (~2.4 GB)\n'
    'legHistogram\n'
    'tripdurations.txt\n'
    'linkstats.txt.gz',
    C_OUT, C_OB, 8)

box(6.9, 8.3, 6, 1.8,
    'Convergence Metrics\n\n'
    'scorestats.txt / .png\n'
    'modestats.txt / .png\n'
    'traveldistancestats.txt\n'
    'stopwatch.txt / .png\n'
    'output_persons.csv.gz',
    C_OUT, C_OB, 8)

box(13.3, 8.3, 6, 1.8,
    'EV-Specific Outputs\n\n'
    'chargers_complete.xml\n'
    'Charger occupancy profiles\n'
    'SoC time profiles\n'
    'Charging behavior scores\n'
    'EV fleet state (per-iter)',
    C_OUT, C_OB, 8)

box(19.7, 8.3, 6, 1.8,
    'Post-Analysis\n(analyze_equity_corridors.py)\n\n'
    'equity_analysis.html\n'
    'corridor_soc_profiles.html\n'
    'charger_utilization.html\n'
    'CSV exports for GIS',
    C_PROC, C_PB, 8)

arrow(3.0, 17.2, 3.4, 10.1)
arrow(9.3, 17.2, 9.9, 10.1)
arrow(15.8, 17.2, 16.3, 10.1)
arrow(22.4, 17.2, 22.7, 10.1)

# ══════════════════════════════════════════════════════════════
# 9. FIRST RUN RESULTS
# ══════════════════════════════════════════════════════════════
header(7.5, '9. FIRST COMPLETED RUN (116K agents, 60 iterations, ~26 hours)')

box(0.3, 5.5, 8.3, 1.5,
    'Score Convergence: GOOD\n'
    'Avg executed: -0.002 -> +0.0008\n'
    'Avg best: steadily rose to +0.0016\n'
    'Stabilized iter 48+ (innovation off 80%)\n'
    'Mode split: 69.2% car / 30.8% walk',
    C_OUT, C_OB, 8)

box(9, 5.5, 8, 1.5,
    'Issues Found\n'
    '75% agents stuck & removed (too aggressive)\n'
    '5,538 "no charger found" errors\n'
    'Crash at iter 60: soc_histogram missing\n'
    'Avg trip distance ~49.4km (stable)',
    C_CHG, C_CB, 8)

box(17.5, 5.5, 8.2, 1.5,
    'Fixes for Production Run\n'
    'stuckTime: 300s -> 900s\n'
    'storageCapacityFactor: 0.06 -> 0.18\n'
    'flowCapacityFactor: 0.02 -> 0.06 (362K)\n'
    'New population: 362K BEV+PHEV agents',
    C_CHG, C_CB, 8)

# ══════════════════════════════════════════════════════════════
# LEGEND
# ══════════════════════════════════════════════════════════════
ly = 4.5
ax.text(13, ly + 0.6, 'LEGEND', ha='center', fontsize=11, fontweight='bold')
items = [
    (C_INPUT, C_IB, 'Raw Input Data'),
    (C_PROC, C_PB, 'Processing / Tools'),
    (C_CHG, C_CB, 'NEW / CHANGED (our work)'),
    (C_OUT, C_OB, 'Generated Outputs'),
    (C_SIM, C_SB, 'Simulation Engine'),
]
for i, (fc, ec, label) in enumerate(items):
    x = 1.5 + i * 4.8
    p = FancyBboxPatch((x, ly - 0.2), 0.6, 0.35, boxstyle='round,pad=0.05',
                        facecolor=fc, edgecolor=ec, linewidth=2)
    ax.add_patch(p)
    ax.text(x + 0.85, ly - 0.03, label, fontsize=8.5, va='center')

ax.text(13, 3.6, 'github.com/Tomal121186621/UrbanEV-MATSim-Maryland',
        ha='center', fontsize=9, color='#888', style='italic')
ax.text(13, 3.2, 'AMD Ryzen 7 2700X (16 threads)  |  128 GB RAM  |  JDK 17  |  MATSim 12.0',
        ha='center', fontsize=8, color='#aaa')

plt.tight_layout(pad=0.5)
plt.savefig('C:/Users/rtomal/Desktop/UrbanEV Maryland/UrbanEV-MATSim-Maryland-main/UrbanEV_Pipeline_Diagram.png',
            dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print('Saved: UrbanEV_Pipeline_Diagram.png')
