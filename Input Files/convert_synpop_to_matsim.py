#!/usr/bin/env python3
"""
Convert synthetic population CSV (one-row-per-trip, 6.6 GB) to MATSim input files
for UrbanEV-v2.  Streams the CSV — never loads full file into memory.

External trips (I-E, E-I, E-E) with (0,0) coordinates are recovered by assigning
through-station coordinates at the network boundary, based on the destination/origin
state FIPS code and the through_stations.csv lookup table.

Outputs:
  1. plans_maryland_ev.xml.gz   — MATSim plans for EV agents
  2. electric_vehicles.xml      — EV fleet definition
  3. vehicletypes.xml           — Vehicle type catalogue
  4. ev_population_summary.csv  — Summary statistics

Usage:
    python convert_synpop_to_matsim.py
"""

import csv
import gzip
import math
import random
import time
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

# ── Configuration ──────────────────────────────────────────────────────────────

random.seed(42)

BASE_DIR = Path(__file__).parent
INPUT_CSV = BASE_DIR / "synthetic_pop_with_coordinates.csv"
THROUGH_STATIONS_CSV = BASE_DIR / "through_stations.csv"
OUTPUT_PLANS = BASE_DIR / "plans_maryland_ev.xml.gz"
OUTPUT_EVS = BASE_DIR / "electric_vehicles.xml"
OUTPUT_VTYPES = BASE_DIR / "vehicletypes.xml"
OUTPUT_SUMMARY = BASE_DIR / "ev_population_summary.csv"

PROGRESS_INTERVAL = 10_000  # print every N EV persons

# Maryland FIPS: 24001-24510, DC FIPS: 11001
INTERNAL_STATE_FIPS = {24, 11}


def is_internal_fips(county_fips: int) -> bool:
    """Return True if county FIPS belongs to MD (24xxx) or DC (11001)."""
    state = county_fips // 1000
    return state in INTERNAL_STATE_FIPS


# ── Income midpoints ($) by hh_income_detailed code 0-9 ───────────────────────

INCOME_MIDPOINTS = {
    0: 7_500, 1: 12_500, 2: 20_000, 3: 30_000, 4: 42_500,
    5: 62_500, 6: 87_500, 7: 125_000, 8: 175_000, 9: 250_000,
}

# ── Activity code → MATSim activity type ──────────────────────────────────────

ACTIVITY_MAP = {1: "home", 2: "work", 4: "school"}  # all others → "other"


def matsim_activity(code: int) -> str:
    return ACTIVITY_MAP.get(code, "other")


# ── Battery capacity (kWh) by ev_model ────────────────────────────────────────

# Usable battery capacity (kWh) — verified against EPA filings, Wikipedia, ev-database.org.
# See ev_specifications_reference.pdf for full citations.
# Values use USABLE (net) capacity for the most common US trim.
BATTERY_CAPACITY = {
    "Model Y": 81, "Model 3": 78, "Model S": 95, "Model X": 95,   # Wikipedia: Tesla specs
    "Cybertruck": 123,                                                # Wikipedia: 123 kWh all variants
    "F-150 Lightning": 131, "Mustang Mach-E": 88,                    # Wikipedia: Extended Range usable
    "Bolt EV": 66, "Bolt EUV": 66, "Equinox EV": 85, "Blazer EV": 85,  # Wikipedia/GM Ultium
    "Silverado EV": 205,                                              # Wikipedia: Max Range
    "Leaf": 39, "Ariya": 87,                                         # Wikipedia: usable (39/87 kWh)
    "Ioniq 5": 74, "Ioniq 6": 74, "Kona Electric": 65,              # ev-database.org: usable
    "ID.4": 77, "EV6": 74, "EV9": 100, "Niro EV": 65,              # Wikipedia/ev-database.org
    "iX": 105, "i4": 81, "i5": 81,                                   # Wikipedia: BMW usable
    "Lyriq": 100, "Hummer EV": 213,                                  # Wikipedia: usable
    "R1S": 135, "R1T": 135,                                          # Wikipedia: Large Pack
    "EQE": 91, "EQS": 108, "EQB": 67,                               # Wikipedia: usable
    "Prologue": 85, "ZDX": 102,                                      # Wikipedia: Ultium
    "bZ4X": 71, "Solterra": 71,                                      # ev-database.org: usable
    "Taycan": 84, "Macan Electric": 95,                               # Wikipedia: usable PB+
    "RZ": 72,                                                         # ev-database.org
}
DEFAULT_BATTERY = 66

# EPA energy consumption (kWh/km) — derived from EPA combined kWh/100mi ratings
# at fueleconomy.gov (2024-2025 model years). Conversion: kWh/100mi / 160.934 = kWh/km.
# See ev_specifications_reference.pdf for full citations.
CONSUMPTION_KWH_PER_KM = {
    "Model Y": 0.180, "Model 3": 0.162, "Model S": 0.174, "Model X": 0.211,  # EPA: 29/26/28/34
    "Cybertruck": 0.255,                                                        # EPA: 41
    "F-150 Lightning": 0.298, "Mustang Mach-E": 0.199,                          # EPA: 48/32
    "Bolt EV": 0.180, "Bolt EUV": 0.180, "Equinox EV": 0.193, "Blazer EV": 0.199,  # EPA: 29/29/31/32
    "Silverado EV": 0.298,                                                      # EPA: 48
    "Leaf": 0.186, "Ariya": 0.205,                                              # EPA: 30/33
    "Ioniq 5": 0.186, "Ioniq 6": 0.149, "Kona Electric": 0.180,                # EPA: 30/24/29
    "ID.4": 0.186, "EV6": 0.180, "EV9": 0.255, "Niro EV": 0.186,              # EPA: 30/29/41/30
    "iX": 0.242, "i4": 0.186, "i5": 0.199,                                     # EPA: 39/30/32
    "Lyriq": 0.249, "Hummer EV": 0.391,                                         # EPA: 40/63
    "R1S": 0.255, "R1T": 0.255,                                                 # EPA: 41/41
    "EQE": 0.217, "EQS": 0.211, "EQB": 0.193,                                  # EPA: 35/34/31
    "Prologue": 0.205, "ZDX": 0.242,                                            # EPA: 33/39
    "bZ4X": 0.174, "Solterra": 0.199,                                           # EPA: 28/32
    "Taycan": 0.242, "Macan Electric": 0.211,                                   # EPA: 39/34
    "RZ": 0.168,                                                                 # EPA: 27
}
DEFAULT_CONSUMPTION = 0.199  # kWh/km (EPA median ~32 kWh/100mi)

# ── Dwelling type mapping ─────────────────────────────────────────────────────

DWELLING_MAP = {
    0: "unknown", 1: "SFD", 2: "SFA", 3: "MF_small",
    4: "MF_medium", 5: "MF_large", 6: "mobile",
}

OWNERSHIP_MAP = {0: "unknown", 1: "own", 2: "rent", 3: "employer", 4: "family"}


# ── Through-station loading & lookup ──────────────────────────────────────────

def load_through_stations(path: Path):
    """Load through_stations.csv and build a state_fips → [station] lookup."""
    stations = []
    state_to_stations = defaultdict(list)  # state FIPS (int) → list of station dicts

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            st = {
                "station_id": row["station_id"],
                "x": float(row["x"]),
                "y": float(row["y"]),
                "direction": row["direction"],
                "highway": row["highway"],
                "target_states": row["target_states"],
            }
            stations.append(st)
            for code in row["target_states"].split(","):
                code = code.strip()
                if code:
                    state_to_stations[int(code)].append(st)

    return stations, dict(state_to_stations)


def find_nearest_station(stations: list, ref_x: float, ref_y: float):
    """Pick the station closest to reference point (ref_x, ref_y)."""
    best = None
    best_dist = float("inf")
    for st in stations:
        d = math.sqrt((st["x"] - ref_x) ** 2 + (st["y"] - ref_y) ** 2)
        if d < best_dist:
            best_dist = d
            best = st
    return best


# ── Derived attribute helpers ─────────────────────────────────────────────────

def derive_home_charger_power(home_type: int, ownership: int, income: int) -> float:
    if home_type == 1:  # SFD
        if ownership == 1:  # own
            if income >= 6:
                return 7.2
            elif income >= 4:
                return 7.2 if random.random() < 0.6 else 1.4
            else:
                return 1.4
        elif ownership == 2:  # rent
            return 1.4 if income >= 5 else 0.0
        else:
            return 1.4
    elif home_type == 2:  # SFA / townhouse
        if ownership == 1:
            return 1.4 if income >= 5 else 0.0
        else:
            return 0.0
    elif home_type in (3, 4, 5):  # apartments
        return 0.0
    elif home_type == 6:  # mobile home
        return 1.4 if ownership == 1 else 0.0
    else:  # 0 / missing
        return 1.4


def derive_work_charger_power(charge_at_work: int) -> float:
    return 7.2 if charge_at_work == 1 else 0.0


def derive_range_anxiety_threshold(income: int, age: int) -> float:
    base = 0.20
    if income <= 2:
        base += 0.10
    elif income <= 4:
        base += 0.05
    if age >= 65:
        base += 0.05
    elif age <= 25:
        base -= 0.03
    return round(min(max(base, 0.10), 0.40), 2)


def derive_beta_money(income: int) -> float:
    midpoint = INCOME_MIDPOINTS.get(income, 62_500)
    beta = -6.0 * (62_500 / max(midpoint, 7_500))
    return round(beta, 3)


def derive_risk_attitude(income: int, age: int) -> str:
    if income >= 7 and age < 50:
        return "risk_neutral"
    elif income <= 3 or age >= 65:
        return "risk_averse"
    else:
        return "moderate"


def derive_smart_charging_aware(income: int, age: int) -> bool:
    prob = 0.30
    if income >= 7:
        prob += 0.25
    elif income >= 5:
        prob += 0.10
    if age <= 40:
        prob += 0.15
    elif age >= 65:
        prob -= 0.10
    return random.random() < min(prob, 0.90)


def derive_value_of_time(income: int, employment: int) -> float:
    midpoint = INCOME_MIDPOINTS.get(income, 62_500)
    hourly_wage = midpoint / 2080
    vot = hourly_wage * 0.5
    if employment in (1, 3, 5, 6, 7, 8, 9):
        vot *= 0.6
    return round(vot, 2)


# ── HHMM integer → seconds from midnight ─────────────────────────────────────

def hhmm_to_seconds(hhmm: int) -> int:
    h = hhmm // 100
    m = hhmm % 100
    return h * 3600 + m * 60


# ── Vehicle type key from model name ──────────────────────────────────────────

def vehicle_type_key(model: str) -> str:
    if not model or model.strip() == "":
        return "default_ev"
    return model.strip().lower().replace(" ", "_").replace("-", "_")


# ── Safe float / int parsing ──────────────────────────────────────────────────

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


# ── XML writing helpers ───────────────────────────────────────────────────────

def fmt_attr(name: str, cls: str, value) -> str:
    return f'        <attribute name="{name}" class="{cls}">{xml_escape(str(value))}</attribute>\n'


def _fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_person_xml(f, person_info: dict, trips: list):
    """Write one <person> element to the gzipped plans XML stream."""
    pid = person_info["person_id"]
    f.write(f'  <person id="{pid}">\n')
    f.write('    <attributes>\n')

    # Demographics
    f.write(fmt_attr("income", "java.lang.Double", person_info["income"]))
    f.write(fmt_attr("age", "java.lang.Integer", person_info["age"]))
    f.write(fmt_attr("dwellingType", "java.lang.String", person_info["dwelling_type"]))
    f.write(fmt_attr("homeOwnership", "java.lang.String", person_info["home_ownership_str"]))
    f.write(fmt_attr("employmentStatus", "java.lang.Integer", person_info["employment_status"]))
    f.write(fmt_attr("evMake", "java.lang.String", person_info["ev_make"]))
    f.write(fmt_attr("evModel", "java.lang.String", person_info["ev_model"]))

    # Derived
    f.write(fmt_attr("rangeAnxietyThreshold", "java.lang.Double", person_info["range_anxiety"]))
    f.write(fmt_attr("homeChargerPower", "java.lang.Double", person_info["home_charger_kw"]))
    f.write(fmt_attr("workChargerPower", "java.lang.Double", person_info["work_charger_kw"]))
    f.write(fmt_attr("smartChargingAware", "java.lang.Boolean",
                      str(person_info["smart_charging"]).lower()))
    f.write(fmt_attr("betaMoney", "java.lang.Double", person_info["beta_money"]))
    f.write(fmt_attr("riskAttitude", "java.lang.String", person_info["risk_attitude"]))
    f.write(fmt_attr("valueOfTime", "java.lang.Double", person_info["value_of_time"]))
    f.write(fmt_attr("subpopulation", "java.lang.String", "nonCriticalSOC"))
    f.write(fmt_attr("hasExternalTrips", "java.lang.Boolean",
                      str(person_info["has_external_trips"]).lower()))

    f.write('    </attributes>\n')
    f.write('    <plan selected="yes">\n')

    # First activity: origin of trip 1
    first = trips[0]
    act_type = matsim_activity(first["o_activity"])
    end_sec = hhmm_to_seconds(first["departure_hhmm"])

    f.write(f'      <activity type="{act_type}" '
            f'x="{first["o_x"]:.4f}" y="{first["o_y"]:.4f}" '
            f'end_time="{_fmt_time(end_sec)}"/>\n')

    for idx, trip in enumerate(trips):
        mode = "car" if trip["travel_mode"] == 4 else "walk"
        f.write(f'      <leg mode="{mode}"/>\n')

        d_act = matsim_activity(trip["d_activity"])
        dx, dy = trip["d_x"], trip["d_y"]

        if idx < len(trips) - 1:
            next_dep = hhmm_to_seconds(trips[idx + 1]["departure_hhmm"])
            f.write(f'      <activity type="{d_act}" '
                    f'x="{dx:.4f}" y="{dy:.4f}" '
                    f'end_time="{_fmt_time(next_dep)}"/>\n')
        else:
            f.write(f'      <activity type="{d_act}" '
                    f'x="{dx:.4f}" y="{dy:.4f}"/>\n')

    f.write('    </plan>\n')
    f.write('  </person>\n')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()

    # ── Load through stations ──
    print(f"Loading through stations from {THROUGH_STATIONS_CSV.name} ...")
    all_stations, state_to_stations = load_through_stations(THROUGH_STATIONS_CSV)
    print(f"  Loaded {len(all_stations)} stations serving "
          f"{len(state_to_stations)} state FIPS codes")
    for st_fips, sts in sorted(state_to_stations.items()):
        names = [s["station_id"] for s in sts]
        print(f"    State {st_fips:02d}: {', '.join(names)}")

    # Accumulators for summary statistics
    stats = {
        "total_rows": 0,
        "ev_rows": 0,
        "ev_persons": 0,
        "ev_trips_written": 0,
        "trips_ii": 0,
        "trips_ie_recovered": 0,
        "trips_ei_recovered": 0,
        "trips_ee_recovered": 0,
        "trips_still_skipped": 0,
        "warnings": 0,
    }
    income_dist = defaultdict(int)
    dwelling_dist = defaultdict(int)
    risk_dist = defaultdict(int)
    vtype_dist = defaultdict(int)
    make_dist = defaultdict(int)
    home_charger_dist = defaultdict(int)
    ext_station_usage = defaultdict(int)  # station_id → count

    vehicle_types_seen = {}
    ev_vehicle_records = []
    summary_rows = []

    # ── Open output plans file ──
    plans_f = gzip.open(OUTPUT_PLANS, "wt", encoding="utf-8", compresslevel=6)
    plans_f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    plans_f.write('<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">\n')
    plans_f.write('<population>\n')

    # ── Stream CSV ──
    print(f"\nReading: {INPUT_CSV}")
    print(f"File size: {INPUT_CSV.stat().st_size / 1e9:.2f} GB")

    current_pid = None
    current_trips = []
    current_person_info = None

    def resolve_external_coords(trip):
        """
        Check if a trip has (0,0) coords and attempt to fix using through stations.

        Returns (trip_dict, trip_class_str) where trip_class is one of:
          'I-I'        — internal, no change needed
          'I-E'        — dest fixed via through station
          'E-I'        — origin fixed via through station
          'E-E'        — both fixed via through stations
          'skip'       — unfixable (no matching station)
          None         — coords were fine, no classification needed
        """
        o_zero = (trip["o_x"] == 0 or trip["o_y"] == 0)
        d_zero = (trip["d_x"] == 0 or trip["d_y"] == 0)

        if not o_zero and not d_zero:
            # Both coords present — classify as I-I (could be I-I with external
            # FIPS but coords already provided by the synthetic pop generator)
            return trip, "I-I"

        o_fips = trip["o_state_county_fips"]
        d_fips = trip["d_state_county_fips"]
        o_internal = is_internal_fips(o_fips)
        d_internal = is_internal_fips(d_fips)

        # Determine trip class based on FIPS
        if o_internal and not d_internal and d_zero:
            # I-E: dest is external with zero coords
            ext_state = d_fips // 1000
            candidates = state_to_stations.get(ext_state)
            if not candidates:
                # Try a fallback: pick the closest station to origin
                candidates = all_stations
            if not candidates:
                return trip, "skip"
            st = find_nearest_station(candidates, trip["o_x"], trip["o_y"])
            trip["d_x"] = st["x"]
            trip["d_y"] = st["y"]
            trip["d_activity"] = 18  # "other" at boundary
            ext_station_usage[st["station_id"]] += 1
            return trip, "I-E"

        elif not o_internal and d_internal and o_zero:
            # E-I: origin is external with zero coords
            ext_state = o_fips // 1000
            candidates = state_to_stations.get(ext_state)
            if not candidates:
                candidates = all_stations
            if not candidates:
                return trip, "skip"
            st = find_nearest_station(candidates, trip["d_x"], trip["d_y"])
            trip["o_x"] = st["x"]
            trip["o_y"] = st["y"]
            trip["o_activity"] = 18  # "other" at boundary
            ext_station_usage[st["station_id"]] += 1
            return trip, "E-I"

        elif not o_internal and not d_internal:
            # E-E: through trip — fix both ends
            fixed = True
            if o_zero:
                ext_state = o_fips // 1000
                candidates = state_to_stations.get(ext_state, all_stations)
                if candidates:
                    # For entry station, use network centroid as reference
                    st = find_nearest_station(candidates, 400000, 150000)
                    trip["o_x"] = st["x"]
                    trip["o_y"] = st["y"]
                    trip["o_activity"] = 18
                    ext_station_usage[st["station_id"]] += 1
                else:
                    fixed = False
            if d_zero:
                ext_state = d_fips // 1000
                candidates = state_to_stations.get(ext_state, all_stations)
                if candidates:
                    ref_x = trip["o_x"] if trip["o_x"] != 0 else 400000
                    ref_y = trip["o_y"] if trip["o_y"] != 0 else 150000
                    st = find_nearest_station(candidates, ref_x, ref_y)
                    trip["d_x"] = st["x"]
                    trip["d_y"] = st["y"]
                    trip["d_activity"] = 18
                    ext_station_usage[st["station_id"]] += 1
                else:
                    fixed = False
            return trip, "E-E" if fixed else "skip"

        else:
            # I-I but with zero coords (data quality issue) or other edge case
            if o_zero or d_zero:
                return trip, "skip"
            return trip, "I-I"

    def flush_person():
        """Process and write the accumulated person if they are an EV agent."""
        nonlocal current_pid, current_trips, current_person_info

        if current_person_info is None or not current_person_info.get("is_ev"):
            return

        # Sort trips by tripno
        current_trips.sort(key=lambda t: t["tripno"])

        # Resolve external trips, filter invalid
        valid_trips = []
        has_external = False
        for t in current_trips:
            t, trip_class = resolve_external_coords(t)
            if trip_class == "skip":
                stats["trips_still_skipped"] += 1
                continue
            # Final validation: both coords must now be non-zero
            if t["o_x"] == 0 or t["o_y"] == 0 or t["d_x"] == 0 or t["d_y"] == 0:
                stats["trips_still_skipped"] += 1
                continue
            valid_trips.append(t)
            if trip_class == "I-I":
                stats["trips_ii"] += 1
            elif trip_class == "I-E":
                stats["trips_ie_recovered"] += 1
                has_external = True
            elif trip_class == "E-I":
                stats["trips_ei_recovered"] += 1
                has_external = True
            elif trip_class == "E-E":
                stats["trips_ee_recovered"] += 1
                has_external = True

        if len(valid_trips) < 1:
            stats["warnings"] += 1
            return

        pid = current_person_info["person_id"]
        home_x = current_person_info["home_x"]
        home_y = current_person_info["home_y"]

        if home_x == 0 or home_y == 0:
            stats["warnings"] += 1
            return

        # ── Derive attributes ──
        income_code = current_person_info["hh_income"]
        age = current_person_info["age"]
        home_type = current_person_info["home_type"]
        ownership = current_person_info["home_ownership"]
        employment = current_person_info["employment_status"]
        charge_at_work = current_person_info["charge_at_work"]
        ev_model = current_person_info["ev_model"]
        ev_make = current_person_info["ev_make"]

        income_midpoint = INCOME_MIDPOINTS.get(income_code, 62_500)
        dwelling_str = DWELLING_MAP.get(home_type, "unknown")
        ownership_str = OWNERSHIP_MAP.get(ownership, "unknown")

        home_charger_kw = derive_home_charger_power(home_type, ownership, income_code)
        work_charger_kw = derive_work_charger_power(charge_at_work)
        range_anxiety = derive_range_anxiety_threshold(income_code, age)
        beta_money = derive_beta_money(income_code)
        risk_att = derive_risk_attitude(income_code, age)
        smart_charging = derive_smart_charging_aware(income_code, age)
        vot = derive_value_of_time(income_code, employment)

        person_info_full = {
            "person_id": pid,
            "income": float(income_midpoint),
            "age": age,
            "dwelling_type": dwelling_str,
            "home_ownership_str": ownership_str,
            "employment_status": employment,
            "ev_make": ev_make,
            "ev_model": ev_model,
            "range_anxiety": range_anxiety,
            "home_charger_kw": home_charger_kw,
            "work_charger_kw": work_charger_kw,
            "smart_charging": smart_charging,
            "beta_money": beta_money,
            "risk_attitude": risk_att,
            "value_of_time": vot,
            "home_x": home_x,
            "home_y": home_y,
            "has_external_trips": has_external,
        }

        write_person_xml(plans_f, person_info_full, valid_trips)

        # ── Electric vehicle record ──
        battery = BATTERY_CAPACITY.get(ev_model, DEFAULT_BATTERY)
        initial_soc = round(battery * random.uniform(0.40, 0.80), 2)
        vtkey = vehicle_type_key(ev_model)

        # Charger type compatibility — must match charger types in chargers.xml
        # and private charger types generated by MobsimScopeEventHandling:
        #   L1  = home chargers at 1.4 kW (private)
        #   L2  = home/work chargers at 7.2 kW (private) + public L2
        #   DCFC = public DC fast chargers (CCS/CHAdeMO)
        #   DCFC_TESLA = Tesla Superchargers (Tesla vehicles only)
        if ev_make.lower() == "tesla":
            charger_types = "L1,L2,DCFC,DCFC_TESLA"
        else:
            charger_types = "L1,L2,DCFC"

        ev_vehicle_records.append({
            "id": pid,
            "battery_capacity": battery,
            "initial_soc": initial_soc,
            "vehicle_type": vtkey,
            "charger_types": charger_types,
        })

        if vtkey not in vehicle_types_seen:
            consumption = CONSUMPTION_KWH_PER_KM.get(ev_model, DEFAULT_CONSUMPTION)
            vehicle_types_seen[vtkey] = (ev_model, battery, consumption)

        # ── Statistics ──
        stats["ev_persons"] += 1
        stats["ev_trips_written"] += len(valid_trips)
        income_dist[income_code] += 1
        dwelling_dist[dwelling_str] += 1
        risk_dist[risk_att] += 1
        vtype_dist[vtkey] += 1
        make_dist[ev_make] += 1
        home_charger_dist[home_charger_kw] += 1

        num_ext = sum(1 for _ in [has_external] if has_external)

        summary_rows.append({
            "person_id": pid,
            "household_id": current_person_info["household_id"],
            "ev_make": ev_make,
            "ev_model": ev_model,
            "battery_kWh": battery,
            "income_bracket": income_code,
            "income_midpoint": income_midpoint,
            "age": age,
            "dwelling_type": dwelling_str,
            "home_ownership": ownership_str,
            "employment_status": employment,
            "home_charger_kw": home_charger_kw,
            "work_charger_kw": work_charger_kw,
            "range_anxiety": range_anxiety,
            "beta_money": beta_money,
            "risk_attitude": risk_att,
            "smart_charging": smart_charging,
            "value_of_time": vot,
            "num_trips": len(valid_trips),
            "num_car_trips": sum(1 for t in valid_trips if t["travel_mode"] == 4),
            "has_external_trips": has_external,
            "home_x": home_x,
            "home_y": home_y,
        })

        if stats["ev_persons"] % PROGRESS_INTERVAL == 0:
            elapsed = time.time() - t0
            print(f"  ... {stats['ev_persons']:,} EV persons processed "
                  f"({stats['total_rows']:,} rows read, {elapsed:.0f}s)")

    # ── Main streaming loop ──
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            stats["total_rows"] += 1
            pid = safe_int(row["person_id"])

            if pid != current_pid:
                # Flush previous person
                if current_pid is not None:
                    flush_person()

                # Start new person
                current_pid = pid
                current_trips = []
                is_ev = safe_int(row.get("assigned_ev")) == 1

                current_person_info = {
                    "person_id": pid,
                    "household_id": safe_int(row.get("household_id")),
                    "is_ev": is_ev,
                    "home_x": safe_float(row.get("home_x")),
                    "home_y": safe_float(row.get("home_y")),
                    "hh_income": safe_int(row.get("hh_income_detailed")),
                    "age": safe_int(row.get("age")),
                    "home_type": safe_int(row.get("home_type")),
                    "home_ownership": safe_int(row.get("home_ownership")),
                    "employment_status": safe_int(row.get("employment_status")),
                    "charge_at_work": safe_int(row.get("charge_at_work_dummy")),
                    "ev_make": (row.get("ev_make") or "").strip(),
                    "ev_model": (row.get("ev_model") or "").strip(),
                }

            # Skip trips for non-EV persons
            if not current_person_info["is_ev"]:
                continue

            stats["ev_rows"] += 1

            # Parse trip (now includes FIPS for external trip resolution)
            trip = {
                "tripno": safe_int(row.get("tripno")),
                "o_activity": safe_int(row.get("o_activity")),
                "d_activity": safe_int(row.get("d_activity")),
                "travel_mode": safe_int(row.get("travel_mode")),
                "departure_hhmm": safe_int(row.get("departure_time_hhmm")),
                "arrival_hhmm": safe_int(row.get("arrival_time_hhmm")),
                "o_x": safe_float(row.get("o_x")),
                "o_y": safe_float(row.get("o_y")),
                "d_x": safe_float(row.get("d_x")),
                "d_y": safe_float(row.get("d_y")),
                "o_state_county_fips": safe_int(row.get("o_state_county_fips")),
                "d_state_county_fips": safe_int(row.get("d_state_county_fips")),
            }
            current_trips.append(trip)

        # Flush last person
        if current_pid is not None:
            flush_person()

    # Close plans XML
    plans_f.write('</population>\n')
    plans_f.close()

    elapsed = time.time() - t0
    print(f"\nStreaming complete: {stats['total_rows']:,} rows in {elapsed:.0f}s")
    print(f"EV persons found: {stats['ev_persons']:,}")
    print(f"EV trips written: {stats['ev_trips_written']:,}")

    # ── Write electric_vehicles.xml ──
    print(f"\nWriting {OUTPUT_EVS.name} ...")
    with open(OUTPUT_EVS, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE vehicles SYSTEM "http://matsim.org/files/dtd/electric_vehicles_v1.dtd">\n')
        f.write('<vehicles>\n')
        for ev in ev_vehicle_records:
            f.write(f'    <vehicle id="{ev["id"]}" '
                    f'battery_capacity="{ev["battery_capacity"]}" '
                    f'initial_soc="{ev["initial_soc"]}" '
                    f'charger_types="{ev["charger_types"]}" '
                    f'vehicle_type="{ev["vehicle_type"]}"/>\n')
        f.write('</vehicles>\n')
    print(f"  Written {len(ev_vehicle_records):,} vehicles")

    # ── Write vehicletypes.xml ──
    print(f"\nWriting {OUTPUT_VTYPES.name} ...")
    with open(OUTPUT_VTYPES, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<vehicleDefinitions xmlns="http://www.matsim.org/files/dtd"\n')
        f.write('    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n')
        f.write('    xsi:schemaLocation="http://www.matsim.org/files/dtd '
                'http://www.matsim.org/files/dtd/vehicleDefinitions_v2.0.xsd">\n')

        for vtkey, (model_name, battery, consumption_kwh_km) in sorted(vehicle_types_seen.items()):
            consumption_kwh_m = consumption_kwh_km / 1000.0
            f.write(f'\n    <vehicleType id="{vtkey}">\n')
            f.write(f'        <attributes>\n')
            f.write(f'            <attribute name="chargerTypes" class="java.lang.String">default</attribute>\n')
            f.write(f'            <attribute name="engeryCapacity" class="java.lang.Double">{battery}</attribute>\n')
            f.write(f'            <attribute name="energyConsumptionPerDistance" '
                    f'class="java.lang.Double">{consumption_kwh_m:.6f}</attribute>\n')
            f.write(f'            <attribute name="vehicleModel" class="java.lang.String">'
                    f'{xml_escape(model_name)}</attribute>\n')
            f.write(f'        </attributes>\n')
            f.write(f'        <capacity seats="5" standingRoomInPersons="0"/>\n')
            f.write(f'        <length meter="4.5"/>\n')
            f.write(f'        <width meter="1.8"/>\n')
            f.write(f'    </vehicleType>\n')

        f.write('\n</vehicleDefinitions>\n')
    print(f"  Written {len(vehicle_types_seen)} vehicle types")

    # ── Write summary CSV ──
    print(f"\nWriting {OUTPUT_SUMMARY.name} ...")
    if summary_rows:
        fieldnames = list(summary_rows[0].keys())
        with open(OUTPUT_SUMMARY, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_rows)
    print(f"  Written {len(summary_rows):,} rows")

    # ── Print final summary ──
    total_elapsed = time.time() - t0
    print(f"\n{'='*70}")
    print(f"CONVERSION COMPLETE — {total_elapsed:.0f}s total")
    print(f"{'='*70}")
    print(f"  Total CSV rows read:     {stats['total_rows']:,}")
    print(f"  EV person rows:          {stats['ev_rows']:,}")
    print(f"  EV persons written:      {stats['ev_persons']:,}")
    print(f"  EV trips written:        {stats['ev_trips_written']:,}")

    print(f"\n  Trip classification:")
    print(f"    I-I (internal):        {stats['trips_ii']:,}")
    print(f"    I-E (recovered):       {stats['trips_ie_recovered']:,}")
    print(f"    E-I (recovered):       {stats['trips_ei_recovered']:,}")
    print(f"    E-E (recovered):       {stats['trips_ee_recovered']:,}")
    recovered = stats["trips_ie_recovered"] + stats["trips_ei_recovered"] + stats["trips_ee_recovered"]
    print(f"    Total recovered:       {recovered:,}")
    print(f"    Still skipped:         {stats['trips_still_skipped']:,}")
    print(f"    Warnings:              {stats['warnings']:,}")

    if ext_station_usage:
        print(f"\n  Through station usage:")
        for sid, cnt in sorted(ext_station_usage.items(), key=lambda x: -x[1]):
            print(f"    {sid}: {cnt:,}")

    ext_persons = sum(1 for r in summary_rows if r.get("has_external_trips"))
    print(f"\n  Persons with external trips: {ext_persons:,} "
          f"({ext_persons / max(len(summary_rows), 1) * 100:.1f}%)")

    print(f"\n  By income bracket:")
    for k in sorted(income_dist):
        label = f"${INCOME_MIDPOINTS[k]:,}" if k in INCOME_MIDPOINTS else "?"
        print(f"    {k} ({label}): {income_dist[k]:,}")

    print(f"\n  By dwelling type:")
    for k in sorted(dwelling_dist):
        print(f"    {k}: {dwelling_dist[k]:,}")

    print(f"\n  By risk attitude:")
    for k in sorted(risk_dist):
        print(f"    {k}: {risk_dist[k]:,}")

    print(f"\n  By home charger (kW):")
    for k in sorted(home_charger_dist):
        print(f"    {k}: {home_charger_dist[k]:,}")

    print(f"\n  By EV make (top 15):")
    for k, v in sorted(make_dist.items(), key=lambda x: -x[1])[:15]:
        print(f"    {k}: {v:,}")

    print(f"\n  By vehicle type (top 15):")
    for k, v in sorted(vtype_dist.items(), key=lambda x: -x[1])[:15]:
        print(f"    {k}: {v:,}")

    print(f"\n  Output files:")
    for p in [OUTPUT_PLANS, OUTPUT_EVS, OUTPUT_VTYPES, OUTPUT_SUMMARY]:
        if p.exists():
            sz = p.stat().st_size
            unit = "MB" if sz > 1e6 else "KB"
            val = sz / 1e6 if sz > 1e6 else sz / 1e3
            print(f"    {p.name}: {val:.1f} {unit}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()
