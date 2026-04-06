#!/usr/bin/env python3
"""
generate_test_scenario.py
=========================
Generates all MATSim / UrbanEV-v2 input files for the integration test.

Network topology
----------------
21 nodes (n0 … n20) on a straight corridor in EPSG:26985.
20 forward links f0 … f19 (n_i → n_{i+1}), each 3 000 m  → 60 km one-way.
20 backward links b0 … b19 (n_{20-i} → n_{19-i}):
  b0 = n20→n19, b1 = n19→n18, …, b19 = n1→n0.
Round-trip distance: 120 km.

Energy budget
-------------
  Leaf  (40 kWh, 671 J/m): trip uses 0.1864×120 = 22.4 kWh  → arrives at ~4 %  SOC (<20 % threshold) ✓ needs charging
  Tesla (75 kWh, 761 J/m): trip uses 0.2114×120 = 25.4 kWh  → arrives at ~26 % SOC (>15 % threshold) ✓ no charging needed
  Bolt  (65 kWh, 645 J/m): trip uses 0.1792×120 = 21.5 kWh  → arrives at ~27 % SOC ✓
  ID.4  (77 kWh, 720 J/m): trip uses 0.2000×120 = 24.0 kWh  → arrives at ~29 % SOC ✓

Usage
-----
python3 generate_test_scenario.py --output-dir test_scenario/
"""

import argparse
import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

N_LINKS     = 20          # number of forward (and backward) links
LINK_LEN_M  = 3_000       # metres per link
FREESPEED   = 27.78       # m/s  (≈ 100 km/h)
ORIGIN_X    = 200_000.0   # EPSG:26985 x of node n0
ORIGIN_Y    = 100_000.0   # EPSG:26985 y of n0 (all nodes on y=ORIGIN_Y)
TOTAL_KM    = N_LINKS * LINK_LEN_M / 1000   # 60 km

# Vehicle type specs: (battery_kWh, consumption_Jpm, charger_types, max_speed_ms)
VEHICLES = {
    "tesla_model_y": (75.0,  761, "L1,L2,DCFC,DCFC_TESLA", 44.44),
    "nissan_leaf":   (40.0,  671, "L1,L2,DCFC",            33.33),
    "chevy_bolt":    (65.0,  645, "L1,L2,DCFC",            33.33),
    "vw_id4":        (77.0,  720, "L1,L2,DCFC",            44.44),
}

INCOME_MIDPOINTS = [7500, 12500, 20000, 30000, 42500,
                    62500, 87500, 125000, 175000, 250000]

# betaMoney formula: -6.0 × (62500 / income_midpoint)
def beta_money(bracket: int) -> float:
    return -6.0 * (62500.0 / INCOME_MIDPOINTS[bracket])

# ── 5 agent groups (n_agents, prefix, vehicle, battery_kWh, init_soc_pct,
#                   income_bracket, home_type_code, risk, age,
#                   home_power_kw, thresh) ─────────────────────────────────────
# Person IDs are: {prefix}{1..n}  — prefixes chosen so validate_test_output.py
# can identify groups via startswith() checks.
GROUPS = [
    # A: high-income, young, SFD, Tesla — should NOT need en-route charging
    dict(label="hi_tesla",    prefix="tesla_",      n=10, vehicle="tesla_model_y",
         batt=75.0, soc=0.60, bracket=7, home_type="1",
         risk="seeking",  age=30, home_power=7.2, thresh=0.15),
    # B: high-income, old, SFD, Leaf — Leaf WILL run out → en-route needed
    dict(label="hi_leaf",     prefix="leaf_hi_",    n=10, vehicle="nissan_leaf",
         batt=40.0, soc=0.60, bracket=7, home_type="1",
         risk="averse",   age=60, home_power=7.2, thresh=0.25),
    # C: low-income, young, MF apartment, Bolt — no home charger
    dict(label="lo_bolt",     prefix="mf_apt_",     n=10, vehicle="chevy_bolt",
         batt=65.0, soc=0.60, bracket=4, home_type="4",
         risk="seeking",  age=30, home_power=0.0, thresh=0.15),
    # D: low-income, old, SFD, Leaf — Leaf WILL run out → en-route needed
    dict(label="lo_leaf",     prefix="leaf_lo_",    n=10, vehicle="nissan_leaf",
         batt=40.0, soc=0.60, bracket=4, home_type="1",
         risk="averse",   age=55, home_power=1.4, thresh=0.25),
    # E: medium-income, mid-age, SFA, VW_ID4
    dict(label="med_id4",     prefix="id4_",        n=10, vehicle="vw_id4",
         batt=77.0, soc=0.60, bracket=5, home_type="2",
         risk="moderate", age=45, home_power=1.4, thresh=0.20),
]

# Charger positions (measured in km from corridor start)
CHARGERS = [
    dict(cid="l2_1",   km=15.0, pwr_kw=7.2,   plugs=4, ctype="L2"),     # 1/4
    dict(cid="dcfc_1", km=20.0, pwr_kw=150.0,  plugs=2, ctype="DCFC"),   # 1/3
    dict(cid="l2_2",   km=30.0, pwr_kw=7.2,   plugs=4, ctype="L2"),     # 1/2
    dict(cid="dcfc_2", km=40.0, pwr_kw=150.0,  plugs=2, ctype="DCFC"),   # 2/3
    dict(cid="l2_3",   km=45.0, pwr_kw=7.2,   plugs=4, ctype="L2"),     # 3/4
]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Network XML
# ─────────────────────────────────────────────────────────────────────────────

def generate_network() -> str:
    nodes = []
    for i in range(N_LINKS + 1):
        x = ORIGIN_X + i * LINK_LEN_M
        nodes.append(f'    <node id="n{i}" x="{x:.1f}" y="{ORIGIN_Y:.1f}"/>')

    links = []
    for i in range(N_LINKS):
        x_mid = ORIGIN_X + (i + 0.5) * LINK_LEN_M
        # Forward
        links.append(
            f'    <link id="f{i}" from="n{i}" to="n{i+1}" '
            f'length="{LINK_LEN_M}" freespeed="{FREESPEED:.2f}" '
            f'capacity="1000" permlanes="1" oneway="1" modes="car"/>')
        # Backward  b0 = n20→n19, b1 = n19→n18, …, b19 = n1→n0
        j = N_LINKS - 1 - i   # j = 19 when i=0, j=0 when i=19
        links.append(
            f'    <link id="b{i}" from="n{N_LINKS-i}" to="n{N_LINKS-i-1}" '
            f'length="{LINK_LEN_M}" freespeed="{FREESPEED:.2f}" '
            f'capacity="1000" permlanes="1" oneway="1" modes="car"/>')

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE network SYSTEM '
        '"http://www.matsim.org/files/dtd/network_v1.dtd">\n'
        '<network name="UrbanEV integration test corridor">\n'
        '  <nodes>\n' + '\n'.join(nodes) + '\n  </nodes>\n'
        '  <links capperiod="01:00:00" effectivecellsize="7.5" effectivelanewidth="3.75">\n'
        + '\n'.join(links) + '\n  </links>\n</network>\n'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Vehicle types XML
# ─────────────────────────────────────────────────────────────────────────────

def generate_vehicletypes() -> str:
    """
    MATSim standard vehicleDefinitions (v2.0 schema) used by the vehicles module.
    UrbanEV reads energy consumption from its own vehicleTypesFile (Sweden format).
    This file just declares the vehicle type IDs so MATSim's mode routing works.
    """
    vt_blocks = []
    for vid, (batt, cons_jpm, _, maxspd) in VEHICLES.items():
        cons_kwh_m = cons_jpm / 3_600_000          # kWh/m
        cons_kwh_per_100km = cons_kwh_m * 100_000  # kWh/100km (for reference)
        vt_blocks.append(f"""\
    <vehicleType id="{vid}">
        <attributes>
            <attribute name="vehicleModel" class="java.lang.String">{vid}</attribute>
        </attributes>
        <capacity seats="5" standingRoomInPersons="0"/>
        <length meter="4.5"/>
        <width meter="1.8"/>
        <maximumVelocity meterPerSecond="{maxspd:.2f}"/>
    </vehicleType>""")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<vehicleDefinitions xmlns="http://www.matsim.org/files/dtd"\n'
        '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '  xsi:schemaLocation="http://www.matsim.org/files/dtd '
        'http://www.matsim.org/files/dtd/vehicleDefinitions_v2.0.xsd">\n'
        + '\n'.join(vt_blocks) + '\n</vehicleDefinitions>\n'
    )


def generate_urbanev_vehicletypes(output_dir: str) -> str:
    """
    UrbanEV-specific vehicletypes (Sweden format) read by ElectricVehicleTypesReader.
    Consumption in kWh/100km, max_charging_rate in C-rate [1/h].
    DOCTYPE references the local DTD shipped with UrbanEV-v2-master.
    """
    # Relative path from output_dir to the UrbanEV DTD
    out = Path(output_dir).resolve()
    dtd = Path(__file__).parent.resolve() / "UrbanEV-v2-master" / "scenarios" / "dtd" / "vehicletypes.dtd"
    try:
        rel_dtd = os.path.relpath(dtd, out)
    except ValueError:
        rel_dtd = str(dtd)  # fallback to absolute on Windows

    lines = []
    for vid, (batt, cons_jpm, _, maxspd) in VEHICLES.items():
        cons_100km = cons_jpm / 3_600_000 * 100_000  # kWh/100km
        # max_charging_rate: C-Rate ≈ max charge power / battery_kWh
        # Use realistic values: L2 = ~7.2kW, DCFC = ~150kW → for simplicity 1.0 C
        max_c = 1.0
        lines.append(
            f'    <type name="{vid}" consumption="{cons_100km:.2f}" '
            f'max_charging_rate="{max_c}" mass="1700" '
            f'width="1.85" height="1.50" length="4.50" '
            f'cw="0.30" ft="0.01" cb="0.191" spr="0.935"/>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<!DOCTYPE vehicletypes SYSTEM "{rel_dtd}">\n'
        '<vehicletypes>\n'
        + '\n'.join(lines)
        + '\n</vehicletypes>\n'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Electric vehicles XML
# ─────────────────────────────────────────────────────────────────────────────

def generate_evehicles() -> str:
    ev_lines = []
    for grp in GROUPS:
        batt   = grp["batt"]
        init   = round(batt * grp["soc"], 3)
        ctypes = VEHICLES[grp["vehicle"]][2]
        vtype  = grp["vehicle"]
        for k in range(grp["n"]):
            pid = f"{grp['prefix']}{k+1}"
            ev_lines.append(
                f'  <vehicle id="{pid}" battery_capacity="{batt}" '
                f'initial_soc="{init}" charger_types="{ctypes}" '
                f'vehicle_type="{vtype}"/>')

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE vehicles SYSTEM "dtd/electric_vehicles_v1.dtd">\n'
        '<vehicles>\n'
        + '\n'.join(ev_lines) + '\n</vehicles>\n'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Chargers XML
# ─────────────────────────────────────────────────────────────────────────────

def generate_chargers(output_dir: str) -> str:
    # DTD path: local UrbanEV chargers.dtd (uses x/y coords, plug_power in kW)
    out = Path(output_dir).resolve()
    dtd = Path(__file__).parent.resolve() / "UrbanEV-v2-master" / "scenarios" / "dtd" / "chargers.dtd"
    try:
        rel_dtd = os.path.relpath(dtd, out)
    except ValueError:
        rel_dtd = str(dtd)

    lines = []
    for c in CHARGERS:
        x = ORIGIN_X + c["km"] * 1000
        lines.append(
            f'  <charger id="{c["cid"]}" x="{x:.1f}" y="{ORIGIN_Y:.1f}" '
            f'type="{c["ctype"]}" plug_power="{c["pwr_kw"]}" '
            f'plug_count="{c["plugs"]}"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<!DOCTYPE chargers SYSTEM "{rel_dtd}">\n'
        '<chargers>\n'
        + '\n'.join(lines) + '\n</chargers>\n'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Plans XML
# ─────────────────────────────────────────────────────────────────────────────

# Forward route f0 … f19  (60 km, ~2160 s at freespeed)
FWD_ROUTE_LINKS = " ".join(f"f{i}" for i in range(N_LINKS))
# Return route  b0 … b19  (n20 → n0, 60 km)
BCK_ROUTE_LINKS = " ".join(f"b{i}" for i in range(N_LINKS))
TRIP_DIST   = N_LINKS * LINK_LEN_M       # 60 000 m
TRAV_TIME_S = int(TRIP_DIST / FREESPEED) # seconds

def _hhmmss(secs: int) -> str:
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

HOME_END_S = 8 * 3600           # 08:00:00
WORK_END_S = 17 * 3600          # 17:00:00

def generate_plans() -> str:
    persons = []
    for grp in GROUPS:
        bm      = beta_money(grp["bracket"])
        for k in range(grp["n"]):
            pid   = f"{grp['prefix']}{k+1}"
            hp    = grp["home_power"]
            thresh= grp["thresh"]
            # employment: 0=Worker (young/mid), 1=Retired (old>=60)
            emp   = 1 if grp["age"] >= 60 else 0

            attrs = (
                f'    <attribute name="betaMoney" class="java.lang.Double">{bm:.4f}</attribute>\n'
                f'    <attribute name="riskAttitude" class="java.lang.String">{grp["risk"]}</attribute>\n'
                f'    <attribute name="rangeAnxietyThreshold" class="java.lang.Double">{thresh}</attribute>\n'
                f'    <attribute name="hh_income_detailed" class="java.lang.Integer">{grp["bracket"]}</attribute>\n'
                f'    <attribute name="home_type" class="java.lang.String">{grp["home_type"]}</attribute>\n'
                f'    <attribute name="employment_status" class="java.lang.Integer">{emp}</attribute>\n'
                + (f'    <attribute name="homeChargerPower" class="java.lang.Double">{hp}</attribute>\n'
                   if hp > 0 else '')
            )

            persons.append(f"""\
  <person id="{pid}">
    <attributes>
{attrs}    </attributes>
    <plan selected="yes">
      <activity type="home" link="f0" x="{ORIGIN_X:.1f}" y="{ORIGIN_Y:.1f}" end_time="{_hhmmss(HOME_END_S)}"/>
      <leg mode="car">
        <route type="links" start_link="f0" end_link="f{N_LINKS-1}" trav_time="{_hhmmss(TRAV_TIME_S)}" distance="{TRIP_DIST:.1f}">{FWD_ROUTE_LINKS}</route>
      </leg>
      <activity type="work" link="f{N_LINKS-1}" x="{ORIGIN_X + TRIP_DIST:.1f}" y="{ORIGIN_Y:.1f}" end_time="{_hhmmss(WORK_END_S)}"/>
      <leg mode="car">
        <route type="links" start_link="f{N_LINKS-1}" end_link="b{N_LINKS-1}" trav_time="{_hhmmss(TRAV_TIME_S)}" distance="{TRIP_DIST:.1f}">{BCK_ROUTE_LINKS}</route>
      </leg>
      <activity type="home" link="f0" x="{ORIGIN_X:.1f}" y="{ORIGIN_Y:.1f}"/>
    </plan>
  </person>""")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE population SYSTEM '
        '"http://www.matsim.org/files/dtd/population_v6.dtd">\n'
        '<population>\n'
        + '\n'.join(persons)
        + '\n</population>\n'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Config XML
# ─────────────────────────────────────────────────────────────────────────────

def generate_config(out_dir: str) -> str:
    # All file references are relative to the config file location
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">
<config>

  <module name="global">
    <param name="randomSeed" value="42"/>
    <param name="coordinateSystem" value="EPSG:26985"/>
    <param name="numberOfThreads" value="1"/>
  </module>

  <module name="network">
    <param name="inputNetworkFile" value="test_network.xml"/>
  </module>

  <module name="plans">
    <param name="inputPlansFile" value="test_plans.xml"/>
    <param name="insistingOnUsingDeprecatedPersonAttributeFile" value="false"/>
  </module>

  <module name="vehicles">
    <param name="vehiclesFile" value="test_vehicletypes.xml"/>
  </module>

  <!-- UrbanEV EV fleet and charging infrastructure -->
  <module name="ev">
    <param name="vehiclesFile" value="test_evehicles.xml"/>
    <param name="chargersFile" value="test_chargers.xml"/>
    <param name="chargeTimeStep" value="60"/>
  </module>

  <module name="controler">
    <param name="firstIteration" value="0"/>
    <param name="lastIteration" value="14"/>
    <param name="outputDirectory" value="test_output"/>
    <param name="writeEventsInterval" value="5"/>
    <param name="writePlansInterval" value="5"/>
    <param name="overwriteFiles" value="deleteDirectoryIfExists"/>
  </module>

  <module name="qsim">
    <param name="startTime" value="00:00:00"/>
    <param name="endTime" value="30:00:00"/>
    <param name="flowCapacityFactor" value="1.0"/>
    <param name="storageCapacityFactor" value="1.0"/>
    <param name="numberOfThreads" value="1"/>
    <param name="snapshotperiod" value="00:00:00"/>
  </module>

  <module name="parallelEventHandling">
    <param name="numberOfThreads" value="1"/>
    <param name="estimatedNumberOfEvents" value="1000000"/>
  </module>

  <module name="planCalcScore">
    <param name="writeExperiencedPlans" value="false"/>
    <parameterset type="scoringParameters">
      <parameterset type="activityParams">
        <param name="activityType" value="home"/>
        <param name="priority" value="1"/>
        <param name="typicalDuration" value="12:00:00"/>
        <param name="minimalDuration" value="01:00:00"/>
      </parameterset>
      <parameterset type="activityParams">
        <param name="activityType" value="work"/>
        <param name="priority" value="1"/>
        <param name="typicalDuration" value="08:00:00"/>
        <param name="openingTime" value="07:00:00"/>
        <param name="closingTime" value="20:00:00"/>
      </parameterset>
      <parameterset type="activityParams">
        <param name="activityType" value="other charging"/>
        <param name="priority" value="1"/>
        <param name="typicalDuration" value="00:30:00"/>
      </parameterset>
      <parameterset type="activityParams">
        <param name="activityType" value="home charging"/>
        <param name="priority" value="1"/>
        <param name="typicalDuration" value="06:00:00"/>
      </parameterset>
      <parameterset type="activityParams">
        <param name="activityType" value="work charging"/>
        <param name="priority" value="1"/>
        <param name="typicalDuration" value="04:00:00"/>
      </parameterset>
      <parameterset type="modeParams">
        <param name="mode" value="car"/>
        <param name="constant" value="0.0"/>
        <param name="marginalUtilityOfTraveling_util_hr" value="-6.0"/>
        <param name="monetaryDistanceRate" value="0.0"/>
      </parameterset>
      <parameterset type="modeParams">
        <param name="mode" value="walk"/>
        <param name="constant" value="0.0"/>
        <param name="marginalUtilityOfTraveling_util_hr" value="-12.0"/>
        <param name="monetaryDistanceRate" value="0.0"/>
      </parameterset>
      <parameterset type="modeParams">
        <param name="mode" value="pt"/>
        <param name="constant" value="0.0"/>
        <param name="marginalUtilityOfTraveling_util_hr" value="-6.0"/>
        <param name="monetaryDistanceRate" value="0.0"/>
      </parameterset>
    </parameterset>
  </module>

  <module name="strategy">
    <param name="maxAgentPlanMemorySize" value="5"/>
    <param name="fractionOfIterationsToDisableInnovation" value="0.80"/>

    <!-- nonCriticalSOC subpopulation -->
    <parameterset type="strategysettings">
      <param name="strategyName" value="SelectExpBeta"/>
      <param name="weight" value="0.5"/>
      <param name="subpopulation" value="nonCriticalSOC"/>
    </parameterset>
    <parameterset type="strategysettings">
      <param name="strategyName" value="ChangeChargingBehaviour"/>
      <param name="weight" value="0.3"/>
      <param name="subpopulation" value="nonCriticalSOC"/>
    </parameterset>
    <parameterset type="strategysettings">
      <param name="strategyName" value="InsertEnRouteCharging"/>
      <param name="weight" value="0.1"/>
      <param name="subpopulation" value="nonCriticalSOC"/>
    </parameterset>
    <parameterset type="strategysettings">
      <param name="strategyName" value="ReRoute"/>
      <param name="weight" value="0.1"/>
      <param name="subpopulation" value="nonCriticalSOC"/>
    </parameterset>

    <!-- criticalSOC subpopulation -->
    <parameterset type="strategysettings">
      <param name="strategyName" value="ChangeChargingBehaviour"/>
      <param name="weight" value="0.4"/>
      <param name="subpopulation" value="criticalSOC"/>
    </parameterset>
    <parameterset type="strategysettings">
      <param name="strategyName" value="InsertEnRouteCharging"/>
      <param name="weight" value="0.5"/>
      <param name="subpopulation" value="criticalSOC"/>
    </parameterset>
    <parameterset type="strategysettings">
      <param name="strategyName" value="ReRoute"/>
      <param name="weight" value="0.1"/>
      <param name="subpopulation" value="criticalSOC"/>
    </parameterset>
  </module>

  <!-- UrbanEV-v2 configuration -->
  <module name="urban_ev">
    <!-- Power-tier pricing (USD/kWh, MD rates) -->
    <param name="publicL1Cost"            value="0.18"/>
    <param name="publicL2Cost"            value="0.25"/>
    <param name="publicDCFCCost"          value="0.48"/>
    <param name="homeChargingCost"        value="0.13"/>
    <param name="workChargingCost"        value="0.0"/>
    <param name="l2PowerThreshold"        value="3.0"/>
    <param name="dcfcPowerThreshold"      value="50.0"/>

    <!-- Sociodemographic heterogeneity -->
    <param name="betaMoney"               value="-6.0"/>
    <param name="alphaScaleCost"          value="1.0"/>
    <param name="usePersonLevelParams"    value="true"/>

    <!-- Value-of-time -->
    <param name="baseValueOfTimeFactor"   value="0.4"/>
    <param name="queueAnnoyanceFactor"    value="2.0"/>
    <param name="detourDisutilityPerHour" value="-6.0"/>

    <!-- En-route charging -->
    <param name="enableEnRouteCharging"   value="true"/>
    <param name="enRouteSearchRadius"     value="5000.0"/>
    <param name="enRouteSafetyBuffer"     value="0.10"/>
    <param name="socProblemThreshold"     value="0.05"/>

    <!-- Range anxiety -->
    <param name="defaultRangeAnxietyThreshold" value="0.2"/>
    <param name="rangeAnxietyUtility"     value="-100.0"/>
    <param name="emptyBatteryUtility"     value="-400.0"/>
    <param name="socDifferenceUtility"    value="-200.0"/>

    <!-- Scoring utilities -->
    <param name="walkingUtility"          value="-0.0001"/>
    <param name="homeChargingUtility"     value="10.0"/>

    <!-- Charger assignment -->
    <param name="parkingSearchRadius"     value="5000"/>
    <param name="defaultHomeChargerPower" value="7.2"/>
    <param name="defaultWorkChargerPower" value="7.2"/>
    <param name="generateHomeChargersByPercentage" value="false"/>
    <param name="generateWorkChargersByPercentage" value="false"/>

    <!-- UrbanEV vehicle types (Sweden format: consumption in kWh/100km) -->
    <param name="vehicleTypesFile"        value="test_urbanev_vehicletypes.xml"/>

    <!-- Smart charging disabled for test simplicity -->
    <param name="enableSmartCharging"     value="false"/>
    <param name="awarenessFactor"         value="0.5"/>

    <!-- Plan mutation limits -->
    <param name="maxNumberSimultaneousPlanChanges" value="1"/>
    <param name="timeAdjustmentProbability"        value="0.5"/>
    <param name="maxTimeFlexibility"               value="600"/>
  </module>

  <module name="TimeAllocationMutator">
    <param name="mutationRange" value="1800"/>
    <param name="mutationAffectsDuration" value="false"/>
  </module>

</config>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate UrbanEV-v2 integration test scenario")
    ap.add_argument("--output-dir", default="test_scenario",
                    help="Directory to write scenario files (created if needed)")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = {
        "test_network.xml":               generate_network(),
        "test_vehicletypes.xml":          generate_vehicletypes(),
        "test_urbanev_vehicletypes.xml":  generate_urbanev_vehicletypes(str(out)),
        "test_evehicles.xml":             generate_evehicles(),
        "test_chargers.xml":              generate_chargers(str(out)),
        "test_plans.xml":                 generate_plans(),
        "test_config.xml":                generate_config(str(out)),
    }

    for fname, content in files.items():
        path = out / fname
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path}  ({len(content):,} bytes)")

    print(f"\nScenario summary:")
    print(f"  {sum(g['n'] for g in GROUPS)} agents, "
          f"{N_LINKS*2} network links, "
          f"{len(CHARGERS)} chargers")
    print(f"  Round-trip distance: {TOTAL_KM*2:.0f} km")
    for grp in GROUPS:
        batt = grp["batt"]
        cons = VEHICLES[grp["vehicle"]][1] / 3_600_000  # kWh/m
        used = cons * TOTAL_KM * 2 * 1000
        end_kwh = batt * grp["soc"] - used
        end_pct = 100 * end_kwh / batt
        print(f"  {grp['label']:12s}: {grp['vehicle']:16s} "
              f"init={batt*grp['soc']:.1f}kWh  "
              f"trip uses={used:.1f}kWh  "
              f"end={end_kwh:.1f}kWh ({end_pct:.0f}%)  "
              f"thresh={grp['thresh']*100:.0f}%  "
              f"{'RANGE ANXIETY' if end_pct < grp['thresh']*100 else 'ok'}")

    print(f"\nRun the simulation with:")
    print(f"  java -cp UrbanEV-v2-master/target/<jar>.jar se.got.GotEVMain "
          f"{out}/test_config.xml 0")


if __name__ == "__main__":
    main()
