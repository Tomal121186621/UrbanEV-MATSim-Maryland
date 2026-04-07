#!/usr/bin/env python3
"""
Convert synthetic_bmc_v3_with_coords.csv (one-row-per-trip) to MATSim input files
for UrbanEV-v2.  Streams the CSV — never loads full file into memory.

Handles both BEV and PHEV agents.  External trips (destinations outside the MATSim
network bounding box) are snapped to through-station coordinates at the network
boundary, based on the destination state FIPS code and through_stations.csv.

Outputs:
  1. plans_maryland_ev.xml.gz   — MATSim plans for EV agents
  2. electric_vehicles.xml      — EV fleet definition
  3. vehicletypes.xml           — Vehicle type catalogue (includes default "car" type)
  4. ev_population_summary.csv  — Summary statistics

Usage:
    python convert_synpop_v3_to_matsim.py
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
INPUT_CSV = BASE_DIR / "synthetic_bmc_v3_with_coords.csv"
THROUGH_STATIONS_CSV = BASE_DIR / "through_stations.csv"
OUTPUT_PLANS = BASE_DIR / "plans_maryland_ev.xml.gz"
OUTPUT_EVS = BASE_DIR / "electric_vehicles.xml"
OUTPUT_VTYPES = BASE_DIR / "vehicletypes.xml"
OUTPUT_SUMMARY = BASE_DIR / "ev_population_summary.csv"

PROGRESS_INTERVAL = 20_000  # print every N EV persons

# MATSim network bounding box (EPSG:26985)
NET_X_MIN, NET_X_MAX = 183_658, 570_205
NET_Y_MIN, NET_Y_MAX = 32_787, 249_470

# Maryland FIPS: 24xxx, DC FIPS: 11xxx
INTERNAL_STATE_FIPS = {24, 11}


def is_internal_fips(county_fips: int) -> bool:
    state = county_fips // 1000
    return state in INTERNAL_STATE_FIPS


def is_inside_network(x: float, y: float, margin: float = 5000) -> bool:
    """Check if coords are within network bounding box (with margin)."""
    return (NET_X_MIN - margin <= x <= NET_X_MAX + margin and
            NET_Y_MIN - margin <= y <= NET_Y_MAX + margin)


# ── Income midpoints ($) by hh_income_detailed code 0-9 ───────────────────────

INCOME_MIDPOINTS = {
    0: 7_500, 1: 12_500, 2: 20_000, 3: 30_000, 4: 42_500,
    5: 62_500, 6: 87_500, 7: 125_000, 8: 175_000, 9: 250_000,
}

# ── Age group → representative age ──────────────────────────────────────────

# RTS codebook: 1=Under5, 2=5-11, 3=12-13, 4=14-15, 5=16-17, 6=18-24,
# 7=25-34, 8=35-44, 9=45-54, 10=55-64, 11=65-74, 12=75-84, 13=85+
AGE_GROUP_MAP = {
    1: 3, 2: 8, 3: 13, 4: 15, 5: 17, 6: 21,
    7: 30, 8: 40, 9: 50, 10: 60, 11: 70, 12: 80, 13: 88,
}

# ── Activity code → MATSim activity type ──────────────────────────────────────

ACTIVITY_MAP = {1: "home", 2: "work", 4: "school"}  # all others → "other"


def matsim_activity(code: int) -> str:
    return ACTIVITY_MAP.get(code, "other")


# ── Battery capacity (kWh) by ev_model ────────────────────────────────────────
# BEV models
BATTERY_CAPACITY = {
    "Model Y": 81, "Model 3": 78, "Model S": 95, "Model X": 95,
    "Cybertruck": 123,
    "F-150 Lightning": 131, "Mustang Mach-E": 88,
    "Bolt EV": 66, "Bolt EUV": 66, "Equinox EV": 85, "Blazer EV": 85,
    "Silverado EV": 205,
    "Leaf": 39, "Ariya": 87,
    "Ioniq 5": 74, "Ioniq 6": 74, "Kona Electric": 65,
    "ID.4": 77, "EV6": 74, "EV9": 100, "Niro EV": 65,
    "iX": 105, "i4": 81, "i5": 81,
    "Lyriq": 100, "Hummer EV": 213,
    "R1S": 135, "R1T": 135,
    "EQE": 91, "EQS": 108, "EQB": 67,
    "Prologue": 85, "ZDX": 102,
    "bZ4X": 71, "Solterra": 71,
    "Taycan": 84, "Macan Electric": 95,
    "RZ": 72,
    # Generic BEV fallback
    "BEV": 66,
    # PHEV models — usable battery (electric-only portion)
    "X5 xDrive50e": 25, "Wrangler 4xe": 17, "Grand Cherokee 4xe": 25,
    "GLC 350e": 16, "XC90 Recharge": 18, "XC60 Recharge": 18,
    "RAV4 Prime": 18, "Prius Prime": 14, "Pacifica PHEV": 16,
    "Outlander PHEV": 20, "Tucson PHEV": 13, "Santa Fe PHEV": 14,
    "Sorento PHEV": 13, "Sportage PHEV": 13, "Escape PHEV": 14,
    "Corsair PHEV": 14, "Aviator PHEV": 19, "Range Rover PHEV": 32,
    "Crosstrek PHEV": 8, "Volvo S60 Recharge": 18, "Volvo S90 Recharge": 18,
    "Q5 TFSI e": 18, "A7 TFSI e": 18, "330e": 12, "X3 xDrive30e": 12,
    "Cayenne E-Hybrid": 18, "Panamera E-Hybrid": 18,
    # Generic PHEV fallback
    "PHEV": 16,
}
DEFAULT_BATTERY = 66
DEFAULT_BATTERY_PHEV = 16

# EPA energy consumption (kWh/km)
CONSUMPTION_KWH_PER_KM = {
    "Model Y": 0.180, "Model 3": 0.162, "Model S": 0.174, "Model X": 0.211,
    "Cybertruck": 0.255,
    "F-150 Lightning": 0.298, "Mustang Mach-E": 0.199,
    "Bolt EV": 0.180, "Bolt EUV": 0.180, "Equinox EV": 0.193, "Blazer EV": 0.199,
    "Silverado EV": 0.298,
    "Leaf": 0.186, "Ariya": 0.205,
    "Ioniq 5": 0.186, "Ioniq 6": 0.149, "Kona Electric": 0.180,
    "ID.4": 0.186, "EV6": 0.180, "EV9": 0.255, "Niro EV": 0.186,
    "iX": 0.242, "i4": 0.186, "i5": 0.199,
    "Lyriq": 0.249, "Hummer EV": 0.391,
    "R1S": 0.255, "R1T": 0.255,
    "EQE": 0.217, "EQS": 0.211, "EQB": 0.193,
    "Prologue": 0.205, "ZDX": 0.242,
    "bZ4X": 0.174, "Solterra": 0.199,
    "Taycan": 0.242, "Macan Electric": 0.211,
    "RZ": 0.168,
    "BEV": 0.199,
    # PHEV — electric-mode consumption (generally higher than BEV due to weight)
    "X5 xDrive50e": 0.280, "Wrangler 4xe": 0.310, "Grand Cherokee 4xe": 0.290,
    "GLC 350e": 0.260, "XC90 Recharge": 0.290, "XC60 Recharge": 0.270,
    "RAV4 Prime": 0.230, "Prius Prime": 0.180, "Pacifica PHEV": 0.310,
    "Outlander PHEV": 0.250, "Tucson PHEV": 0.240, "Santa Fe PHEV": 0.260,
    "Sorento PHEV": 0.260, "Sportage PHEV": 0.250, "Escape PHEV": 0.230,
    "Corsair PHEV": 0.250, "Aviator PHEV": 0.300, "Range Rover PHEV": 0.330,
    "Crosstrek PHEV": 0.220, "Volvo S60 Recharge": 0.260, "Volvo S90 Recharge": 0.270,
    "Q5 TFSI e": 0.260, "A7 TFSI e": 0.250, "330e": 0.230, "X3 xDrive30e": 0.250,
    "Cayenne E-Hybrid": 0.310, "Panamera E-Hybrid": 0.280,
    "PHEV": 0.260,
}
DEFAULT_CONSUMPTION = 0.199
DEFAULT_CONSUMPTION_PHEV = 0.260

# ── Dwelling type mapping ─────────────────────────────────────────────────────

DWELLING_MAP = {
    0: "unknown", 1: "SFD", 2: "SFA", 3: "MF_small",
    4: "MF_medium", 5: "MF_large", 6: "mobile",
}
OWNERSHIP_MAP = {0: "unknown", 1: "own", 2: "rent", 3: "employer", 4: "family"}


# ── Through-station loading & lookup ──────────────────────────────────────────

def load_through_stations(path: Path):
    stations = []
    state_to_stations = defaultdict(list)
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
            if income >= 6: return 7.2
            elif income >= 4: return 7.2 if random.random() < 0.6 else 1.4
            else: return 1.4
        elif ownership == 2:  # rent
            return 1.4 if income >= 5 else 0.0
        else: return 1.4
    elif home_type == 2:  # SFA/townhouse
        if ownership == 1: return 1.4 if income >= 5 else 0.0
        else: return 0.0
    elif home_type in (3, 4, 5):  # apartments
        return 0.0
    elif home_type == 6:  # mobile
        return 1.4 if ownership == 1 else 0.0
    else:
        return 1.4


def derive_work_charger_power(j1_ev_charging: int) -> float:
    return 7.2 if j1_ev_charging == 1 else 0.0


def derive_range_anxiety_threshold(income: int, age: int) -> float:
    base = 0.20
    if income <= 2: base += 0.10
    elif income <= 4: base += 0.05
    if age >= 65: base += 0.05
    elif age <= 25: base -= 0.03
    return round(min(max(base, 0.10), 0.40), 2)


def derive_beta_money(income: int) -> float:
    midpoint = INCOME_MIDPOINTS.get(income, 62_500)
    return round(-6.0 * (62_500 / max(midpoint, 7_500)), 3)


def derive_risk_attitude(income: int, age: int) -> str:
    if income >= 7 and age < 50: return "risk_neutral"
    elif income <= 3 or age >= 65: return "risk_averse"
    else: return "moderate"


def derive_smart_charging_aware(income: int, age: int) -> bool:
    prob = 0.30
    if income >= 7: prob += 0.25
    elif income >= 5: prob += 0.10
    if age <= 40: prob += 0.15
    elif age >= 65: prob -= 0.10
    return random.random() < min(prob, 0.90)


def derive_value_of_time(income: int, employment: int) -> float:
    midpoint = INCOME_MIDPOINTS.get(income, 62_500)
    vot = (midpoint / 2080) * 0.5
    if employment in (1, 3, 5, 6, 7, 8, 9): vot *= 0.6
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


# ── Safe parsing ──────────────────────────────────────────────────────────────

def safe_float(val, default=0.0):
    try: return float(val)
    except (ValueError, TypeError): return default


def safe_int(val, default=0):
    try: return int(float(val))
    except (ValueError, TypeError): return default


# ── XML writing helpers ───────────────────────────────────────────────────────

def fmt_attr(name: str, cls: str, value) -> str:
    return f'        <attribute name="{name}" class="{cls}">{xml_escape(str(value))}</attribute>\n'


def _fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_person_xml(f, person_info: dict, trips: list):
    pid = person_info["person_id"]
    f.write(f'  <person id="{pid}">\n')
    f.write('    <attributes>\n')
    f.write(fmt_attr("income", "java.lang.Double", person_info["income"]))
    f.write(fmt_attr("hh_income_detailed", "java.lang.Integer", person_info["hh_income"]))
    f.write(fmt_attr("age", "java.lang.Integer", person_info["age"]))
    f.write(fmt_attr("dwellingType", "java.lang.String", person_info["dwelling_type"]))
    f.write(fmt_attr("homeOwnership", "java.lang.String", person_info["home_ownership_str"]))
    f.write(fmt_attr("employmentStatus", "java.lang.Integer", person_info["employment_status"]))
    f.write(fmt_attr("evMake", "java.lang.String", person_info["ev_make"]))
    f.write(fmt_attr("evModel", "java.lang.String", person_info["ev_model"]))
    f.write(fmt_attr("evType", "java.lang.String", person_info["ev_type"]))
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

    stats = {
        "total_rows": 0, "ev_rows": 0, "ev_persons": 0,
        "ev_trips_written": 0, "trips_ii": 0,
        "trips_snapped_origin": 0, "trips_snapped_dest": 0,
        "trips_snapped_both": 0, "trips_skipped": 0, "warnings": 0,
        "bev_persons": 0, "phev_persons": 0,
        "skipped_no_car": 0, "skipped_no_ev_slot": 0,
    }
    income_dist = defaultdict(int)
    dwelling_dist = defaultdict(int)
    risk_dist = defaultdict(int)
    vtype_dist = defaultdict(int)
    make_dist = defaultdict(int)
    home_charger_dist = defaultdict(int)
    ext_station_usage = defaultdict(int)

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

    def snap_to_network(trip):
        """
        Check if trip origin/destination is outside the network bounding box.
        If so, snap to nearest through station based on state FIPS.
        Returns (trip, classification) where classification is:
          'I-I', 'snapped_dest', 'snapped_origin', 'snapped_both', 'skip'
        """
        ox, oy = trip["o_x"], trip["o_y"]
        dx, dy = trip["d_x"], trip["d_y"]

        o_outside = not is_inside_network(ox, oy)
        d_outside = not is_inside_network(dx, dy)

        if not o_outside and not d_outside:
            return trip, "I-I"

        d_fips = trip["d_state_county_fips"]
        home_fips = trip["home_state_county_fips"]

        if not o_outside and d_outside:
            # Internal origin, external dest — snap dest
            ext_state = d_fips // 1000 if d_fips > 0 else 0
            candidates = state_to_stations.get(ext_state, all_stations)
            if not candidates:
                return trip, "skip"
            st = find_nearest_station(candidates, ox, oy)
            trip["d_x"] = st["x"]
            trip["d_y"] = st["y"]
            ext_station_usage[st["station_id"]] += 1
            return trip, "snapped_dest"

        elif o_outside and not d_outside:
            # External origin, internal dest — snap origin
            ext_state = home_fips // 1000 if home_fips > 0 else 0
            candidates = state_to_stations.get(ext_state, all_stations)
            if not candidates:
                return trip, "skip"
            st = find_nearest_station(candidates, dx, dy)
            trip["o_x"] = st["x"]
            trip["o_y"] = st["y"]
            ext_station_usage[st["station_id"]] += 1
            return trip, "snapped_origin"

        else:
            # Both outside — snap both
            fixed = True
            ext_state_o = home_fips // 1000 if home_fips > 0 else 0
            candidates_o = state_to_stations.get(ext_state_o, all_stations)
            if candidates_o:
                st = find_nearest_station(candidates_o, 400000, 150000)
                trip["o_x"] = st["x"]
                trip["o_y"] = st["y"]
                ext_station_usage[st["station_id"]] += 1
            else:
                fixed = False

            ext_state_d = d_fips // 1000 if d_fips > 0 else 0
            candidates_d = state_to_stations.get(ext_state_d, all_stations)
            if candidates_d:
                ref_x = trip["o_x"] if trip["o_x"] != 0 else 400000
                ref_y = trip["o_y"] if trip["o_y"] != 0 else 150000
                st = find_nearest_station(candidates_d, ref_x, ref_y)
                trip["d_x"] = st["x"]
                trip["d_y"] = st["y"]
                ext_station_usage[st["station_id"]] += 1
            else:
                fixed = False

            return trip, "snapped_both" if fixed else "skip"

    def flush_person_final(pinfo, valid_trips, has_external,
                           ev_make, ev_model, ev_type, rank):
        """Write one EV agent with assigned EV specs."""

        pid = pinfo["person_id"]
        home_x = pinfo["home_x"]
        home_y = pinfo["home_y"]

        income_code = pinfo["hh_income"]
        age = pinfo["age"]
        home_type = pinfo["home_type"]
        ownership = pinfo["home_ownership"]
        employment = pinfo["employment_status"]
        j1_ev_charging = pinfo["j1_ev_charging"]

        income_midpoint = INCOME_MIDPOINTS.get(income_code, 62_500)
        dwelling_str = DWELLING_MAP.get(home_type, "unknown")
        ownership_str = OWNERSHIP_MAP.get(ownership, "unknown")

        home_charger_kw = derive_home_charger_power(home_type, ownership, income_code)
        work_charger_kw = derive_work_charger_power(j1_ev_charging)
        range_anxiety = derive_range_anxiety_threshold(income_code, age)
        beta_money = derive_beta_money(income_code)
        risk_att = derive_risk_attitude(income_code, age)
        smart_charging = derive_smart_charging_aware(income_code, age)
        vot = derive_value_of_time(income_code, employment)

        person_info_full = {
            "person_id": pid,
            "income": float(income_midpoint),
            "hh_income": income_code,
            "age": age,
            "dwelling_type": dwelling_str,
            "home_ownership_str": ownership_str,
            "employment_status": employment,
            "ev_make": ev_make,
            "ev_model": ev_model,
            "ev_type": ev_type,
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
        is_phev = (ev_type == "PHEV")
        battery = BATTERY_CAPACITY.get(ev_model,
                    DEFAULT_BATTERY_PHEV if is_phev else DEFAULT_BATTERY)

        # Primary driver (rank 0): use ev1_battery_kwh from CSV if available
        # Secondary drivers (rank 1+): use lookup table only (generic specs)
        if rank == 0:
            csv_battery = pinfo.get("ev1_battery_kwh", 0)
            if csv_battery > 5:
                battery = round(csv_battery)

        initial_soc = round(battery * random.uniform(0.40, 0.80), 2)
        vtkey = vehicle_type_key(ev_model)

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
            consumption = CONSUMPTION_KWH_PER_KM.get(ev_model,
                            DEFAULT_CONSUMPTION_PHEV if is_phev else DEFAULT_CONSUMPTION)
            vehicle_types_seen[vtkey] = (ev_model, battery, consumption)

        stats["ev_persons"] += 1
        if is_phev:
            stats["phev_persons"] += 1
        else:
            stats["bev_persons"] += 1
        stats["ev_trips_written"] += len(valid_trips)
        income_dist[income_code] += 1
        dwelling_dist[dwelling_str] += 1
        risk_dist[risk_att] += 1
        vtype_dist[vtkey] += 1
        make_dist[ev_make] += 1
        home_charger_dist[home_charger_kw] += 1

        summary_rows.append({
            "person_id": pid,
            "household_id": pinfo["household_id"],
            "ev_make": ev_make, "ev_model": ev_model, "ev_type": ev_type,
            "battery_kWh": battery,
            "income_bracket": income_code, "income_midpoint": income_midpoint,
            "age": age, "dwelling_type": dwelling_str,
            "home_ownership": ownership_str,
            "employment_status": employment,
            "home_charger_kw": home_charger_kw,
            "work_charger_kw": work_charger_kw,
            "range_anxiety": range_anxiety,
            "beta_money": beta_money, "risk_attitude": risk_att,
            "smart_charging": smart_charging, "value_of_time": vot,
            "num_trips": len(valid_trips),
            "num_car_trips": sum(1 for t in valid_trips if t["travel_mode"] == 4),
            "has_external_trips": has_external,
            "home_x": home_x, "home_y": home_y,
        })

        if stats["ev_persons"] % PROGRESS_INTERVAL == 0:
            elapsed = time.time() - t0
            print(f"  ... {stats['ev_persons']:,} EV persons processed "
                  f"({stats['total_rows']:,} rows read, {elapsed:.0f}s)")

    # ── Household-level EV assignment ──────────────────────────────────────
    # Phase 1: Stream CSV, collect all EV persons grouped by household.
    # Phase 2: For each household, assign EVs to the top ev_count drivers
    #          (ranked by number of car trips). Primary driver gets ev1 specs,
    #          secondary drivers get generic BEV/PHEV specs.

    print("\nPhase 1: Collecting EV persons by household...")
    # hh_id -> list of (person_info, trips)
    household_persons = defaultdict(list)
    household_ev_count = {}  # hh_id -> ev_count

    current_pid = None
    current_trips = []
    current_person_info = None

    def collect_person():
        """Collect person into household bucket (don't write yet)."""
        nonlocal current_pid, current_trips, current_person_info
        if current_person_info is None or not current_person_info.get("is_ev"):
            return
        hh_id = current_person_info["household_id"]
        household_persons[hh_id].append((current_person_info, list(current_trips)))
        if hh_id not in household_ev_count:
            household_ev_count[hh_id] = safe_int(current_person_info.get("ev_count", 1))
            if household_ev_count[hh_id] < 1:
                household_ev_count[hh_id] = 1

    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["total_rows"] += 1
            hh_id = row.get("household_id", "")
            p_slot = row.get("person_slot", "")
            pid = f"{hh_id}_{p_slot}"

            if pid != current_pid:
                if current_pid is not None:
                    collect_person()
                current_pid = pid
                current_trips = []
                is_ev = row.get("has_ev", "0") == "1"

                ev_model = (row.get("ev1_model") or "").strip()
                ev_make = (row.get("ev1_make") or "").strip()
                ev_type = (row.get("ev1_type") or "").strip()
                age_group = safe_int(row.get("age_group"))
                age = AGE_GROUP_MAP.get(age_group, 45)

                current_person_info = {
                    "person_id": pid,
                    "household_id": hh_id,
                    "is_ev": is_ev,
                    "home_x": safe_float(row.get("home_x")),
                    "home_y": safe_float(row.get("home_y")),
                    "hh_income": safe_int(row.get("hh_income_detailed")),
                    "age": age,
                    "home_type": safe_int(row.get("home_type")),
                    "home_ownership": safe_int(row.get("home_ownership")),
                    "employment_status": safe_int(row.get("employment_status")),
                    "j1_ev_charging": safe_int(row.get("j1_benefits_ev_charging")),
                    "ev_make": ev_make,
                    "ev_model": ev_model,
                    "ev_type": ev_type,
                    "ev_count": safe_int(row.get("ev_count", 1)),
                    "ev1_battery_kwh": safe_float(row.get("ev1_battery_kwh")),
                    "home_state_county_fips": safe_int(row.get("home_state_county_fips")),
                }

            if not current_person_info["is_ev"]:
                continue

            stats["ev_rows"] += 1
            trip = {
                "tripno": safe_int(row.get("subtour_tripno")),
                "o_activity": safe_int(row.get("o_activity")),
                "d_activity": safe_int(row.get("d_activity")),
                "travel_mode": safe_int(row.get("travel_mode")),
                "departure_hhmm": safe_int(row.get("departure_time_hhmm")),
                "o_x": safe_float(row.get("o_x")),
                "o_y": safe_float(row.get("o_y")),
                "d_x": safe_float(row.get("d_x")),
                "d_y": safe_float(row.get("d_y")),
                "d_state_county_fips": safe_int(row.get("d_state_county_fips")),
                "home_state_county_fips": current_person_info["home_state_county_fips"],
            }
            current_trips.append(trip)

        if current_pid is not None:
            collect_person()

    elapsed_p1 = time.time() - t0
    total_hh = len(household_persons)
    total_ev_persons_collected = sum(len(v) for v in household_persons.values())
    print(f"  Phase 1 complete: {total_ev_persons_collected:,} EV persons in "
          f"{total_hh:,} households ({elapsed_p1:.0f}s)")

    # ── Phase 2: Assign EVs per household and write ──
    print("\nPhase 2: Assigning EVs to top drivers per household...")

    for hh_id, persons_list in household_persons.items():
        ev_count = household_ev_count.get(hh_id, 1)

        # Count car trips per person and filter to drivers only
        person_car_trips = []
        for pinfo, trips in persons_list:
            # Resolve external trips
            valid_trips = []
            has_external = False
            for t in sorted(trips, key=lambda x: x["tripno"]):
                t, trip_class = snap_to_network(t)
                if trip_class == "skip":
                    stats["trips_skipped"] += 1
                    continue
                if t["o_x"] == 0 or t["o_y"] == 0 or t["d_x"] == 0 or t["d_y"] == 0:
                    stats["trips_skipped"] += 1
                    continue
                valid_trips.append(t)
                if trip_class == "I-I":
                    stats["trips_ii"] += 1
                elif trip_class in ("snapped_dest", "snapped_origin", "snapped_both"):
                    stats[f"trips_{trip_class}"] += 1
                    has_external = True

            if not valid_trips:
                stats["warnings"] += 1
                continue

            num_car = sum(1 for t in valid_trips if t["travel_mode"] == 4)
            if num_car == 0:
                stats["skipped_no_car"] += 1
                continue

            if pinfo["home_x"] == 0 or pinfo["home_y"] == 0:
                stats["warnings"] += 1
                continue

            person_car_trips.append((pinfo, valid_trips, num_car, has_external))

        if not person_car_trips:
            continue

        # Sort by car trips descending — top drivers get EVs
        person_car_trips.sort(key=lambda x: -x[2])

        # Assign EVs: top ev_count persons get vehicles
        for rank, (pinfo, valid_trips, num_car, has_external) in enumerate(person_car_trips):
            if rank >= ev_count:
                stats["skipped_no_ev_slot"] += 1
                continue

            # Primary driver (rank 0) gets ev1 specs from CSV
            # Secondary drivers (rank 1+) get generic type based on ev1_type
            if rank == 0:
                ev_model = pinfo["ev_model"]
                ev_make = pinfo["ev_make"]
                ev_type = pinfo["ev_type"]
            else:
                # Secondary driver: generic BEV or PHEV
                ev_type = pinfo["ev_type"] if pinfo["ev_type"] in ("BEV", "PHEV") else "BEV"
                ev_model = ev_type  # "BEV" or "PHEV"
                ev_make = "Other"

            flush_person_final(pinfo, valid_trips, has_external,
                               ev_make, ev_model, ev_type, rank)

    plans_f.write('</population>\n')
    plans_f.close()

    elapsed = time.time() - t0
    print(f"\nStreaming complete: {stats['total_rows']:,} rows in {elapsed:.0f}s")

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

        # Default "car" vehicle type required by MATSim PrepareForSim
        f.write('\n    <!-- Default vehicle type for "car" network mode -->\n')
        f.write('    <vehicleType id="car">\n')
        f.write('        <attributes>\n')
        f.write('            <attribute name="chargerTypes" class="java.lang.String">default</attribute>\n')
        f.write('        </attributes>\n')
        f.write('        <capacity seats="5" standingRoomInPersons="0"/>\n')
        f.write('        <length meter="4.5"/>\n')
        f.write('        <width meter="1.8"/>\n')
        f.write('        <maximumVelocity meterPerSecond="33.33"/>\n')
        f.write('    </vehicleType>\n')

        for vtkey, (model_name, battery, consumption_kwh_km) in sorted(vehicle_types_seen.items()):
            consumption_kwh_m = consumption_kwh_km / 1000.0
            f.write(f'\n    <vehicleType id="{xml_escape(vtkey)}">\n')
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
    print(f"  Written {len(vehicle_types_seen) + 1} vehicle types (incl. default car)")

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
    print(f"    BEV persons:           {stats['bev_persons']:,}")
    print(f"    PHEV persons:          {stats['phev_persons']:,}")
    print(f"  EV trips written:        {stats['ev_trips_written']:,}")
    print(f"  Skipped (no car trips):  {stats['skipped_no_car']:,}")
    print(f"  Skipped (no EV slot):    {stats['skipped_no_ev_slot']:,}")

    print(f"\n  Trip classification:")
    print(f"    Internal (I-I):        {stats['trips_ii']:,}")
    print(f"    Snapped dest:          {stats['trips_snapped_dest']:,}")
    print(f"    Snapped origin:        {stats['trips_snapped_origin']:,}")
    print(f"    Snapped both:          {stats['trips_snapped_both']:,}")
    snapped = stats["trips_snapped_dest"] + stats["trips_snapped_origin"] + stats["trips_snapped_both"]
    print(f"    Total snapped:         {snapped:,}")
    print(f"    Skipped:               {stats['trips_skipped']:,}")
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
