#!/usr/bin/env python3
"""
Convert AFDC (Alternative Fuels Data Center) CSV exports to MATSim chargers.xml
for UrbanEV-v2.

Usage:
    python convert_afdc_to_chargers_xml.py
"""

import csv
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

from pyproj import Transformer

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

CSV_FILES = [
    BASE_DIR / "alt_fuel_stations (Mar 1 2026)_MD.csv",
    BASE_DIR / "alt_fuel_stations (Mar 1 2026)_DC.csv",
]

NETWORK_FILE = BASE_DIR / "maryland-dc-ev-network.xml.gz"
OUTPUT_XML = BASE_DIR / "chargers.xml"
OUTPUT_CSV = BASE_DIR / "chargers_metadata.csv"

# DCFC power defaults by network (kW)
DCFC_POWER = {
    "Tesla":              150,
    "Tesla Supercharger":  150,
    "EVgo":               100,
    "Electrify America":  150,
    "ChargePoint Network": 62.5,
    "ChargePoint":         62.5,
}
DCFC_POWER_DEFAULT = 50

L2_POWER_DEFAULT = 7.2
L2_POWER_TESLA_DEST = 11.5


# ── Helpers ────────────────────────────────────────────────────────────────────

def detect_network_crs(network_path: Path) -> str:
    """Read the CRS from the MATSim network XML header."""
    opener = gzip.open if network_path.suffix == ".gz" else open
    with opener(network_path, "rt") as f:
        for line in f:
            if "coordinateReferenceSystem" in line:
                # Extract EPSG code from attribute value
                start = line.index(">") + 1
                end = line.index("</")
                return line[start:end].strip()
            if "<nodes>" in line:
                break
    raise RuntimeError("Could not detect CRS from network file")


def safe_int(val):
    """Parse an integer from a CSV field that may be empty or float-like."""
    if not val or val.strip() == "":
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def is_tesla_destination(row):
    """Check if station is a Tesla Destination (L2) charger, not a Supercharger."""
    network = (row.get("EV Network") or "").strip()
    # Tesla Destination chargers are networked as "Tesla Destination"
    if "destination" in network.lower():
        return True
    # If network is just "Tesla" and it only has L2 (no DCFC), it's a Destination
    if network.lower() == "tesla" and safe_int(row.get("EV DC Fast Count")) == 0:
        return True
    return False


def dcfc_power_for_network(network: str) -> float:
    """Return DCFC plug power based on network name."""
    network_clean = network.strip()
    for key, power in DCFC_POWER.items():
        if key.lower() in network_clean.lower():
            return power
    return DCFC_POWER_DEFAULT


def classify_dcfc_type(connector_types: str, network: str) -> str:
    """
    Return 'DCFC' or 'DCFC_TESLA' based on connector availability.
    If the station ONLY has Tesla connectors (no CCS, no CHAdeMO), it's DCFC_TESLA.
    """
    ct = (connector_types or "").upper()
    has_tesla = "TESLA" in ct
    has_ccs = "CCS" in ct or "COMBO" in ct
    has_chademo = "CHADEMO" in ct

    if has_tesla and not has_ccs and not has_chademo:
        return "DCFC_TESLA"
    return "DCFC"


# ── Main processing ───────────────────────────────────────────────────────────

def main():
    # 1. Detect network CRS
    network_crs = detect_network_crs(NETWORK_FILE)
    print(f"Network CRS detected: {network_crs}")

    # Set up coordinate transformer: WGS84 → network CRS
    transformer = Transformer.from_crs("EPSG:4326", network_crs, always_xy=True)

    # 2. Read and filter stations from all CSVs
    all_chargers = []       # list of dicts for XML output
    metadata_rows = []      # list of dicts for CSV output
    stats = defaultdict(int)
    counters = defaultdict(int)  # for sequential IDs per type+state

    for csv_path in CSV_FILES:
        print(f"\n{'='*70}")
        print(f"Processing: {csv_path.name}")
        print(f"{'='*70}")

        file_stats = defaultdict(int)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_stats["total"] += 1

                # ── Filters ──

                # Must be EV station
                if (row.get("Fuel Type Code") or "").strip() != "ELEC":
                    file_stats["skip_not_elec"] += 1
                    continue

                # Status must be E (existing)
                status = (row.get("Status Code") or "").strip().upper()
                if status != "E":
                    file_stats["skip_status"] += 1
                    continue

                # Must be public access
                access = (row.get("Access Code") or "").strip().lower()
                if "public" not in access:
                    file_stats["skip_access"] += 1
                    continue

                # Valid coordinates
                try:
                    lat = float(row.get("Latitude") or 0)
                    lon = float(row.get("Longitude") or 0)
                except (ValueError, TypeError):
                    file_stats["skip_coords"] += 1
                    continue
                if lat == 0 or lon == 0:
                    file_stats["skip_coords"] += 1
                    continue

                # Exclude Tesla Destination chargers
                if is_tesla_destination(row):
                    file_stats["skip_tesla_dest"] += 1
                    continue

                # ── Parse port counts ──
                l2_count = safe_int(row.get("EV Level2 EVSE Num"))
                dcfc_count = safe_int(row.get("EV DC Fast Count"))

                if l2_count == 0 and dcfc_count == 0:
                    file_stats["skip_no_ports"] += 1
                    continue

                # ── Coordinate transform ──
                x, y = transformer.transform(lon, lat)

                network = (row.get("EV Network") or "").strip()
                connectors = (row.get("EV Connector Types") or "").strip()
                state = (row.get("State") or "").strip().upper()
                station_name = (row.get("Station Name") or "").strip()
                address = (row.get("Street Address") or "").strip()
                city = (row.get("City") or "").strip()
                facility_type = (row.get("Facility Type") or "").strip()

                file_stats["stations_kept"] += 1

                # ── Create L2 charger entry ──
                if l2_count > 0:
                    counters[("l2", state)] += 1
                    seq = counters[("l2", state)]
                    charger_id = f"l2_{state}_{seq:04d}"
                    plug_power = L2_POWER_DEFAULT

                    charger = {
                        "id": charger_id,
                        "type": "L2",
                        "plug_count": l2_count,
                        "plug_power": plug_power,
                        "x": x,
                        "y": y,
                    }
                    all_chargers.append(charger)

                    metadata_rows.append({
                        "charger_id": charger_id,
                        "station_name": station_name,
                        "address": address,
                        "city": city,
                        "state": state,
                        "latitude": lat,
                        "longitude": lon,
                        "x_projected": round(x, 4),
                        "y_projected": round(y, 4),
                        "level": "L2",
                        "plug_power_kw": plug_power,
                        "plug_count": l2_count,
                        "ev_network": network,
                        "connector_types": connectors,
                        "facility_type": facility_type,
                    })

                    stats["l2_total"] += 1
                    stats[f"l2_{state}"] += 1

                # ── Create DCFC charger entry ──
                if dcfc_count > 0:
                    counters[("dcfc", state)] += 1
                    seq = counters[("dcfc", state)]
                    charger_id = f"dcfc_{state}_{seq:04d}"
                    plug_power = dcfc_power_for_network(network)
                    charger_type = classify_dcfc_type(connectors, network)

                    charger = {
                        "id": charger_id,
                        "type": charger_type,
                        "plug_count": dcfc_count,
                        "plug_power": plug_power,
                        "x": x,
                        "y": y,
                    }
                    all_chargers.append(charger)

                    metadata_rows.append({
                        "charger_id": charger_id,
                        "station_name": station_name,
                        "address": address,
                        "city": city,
                        "state": state,
                        "latitude": lat,
                        "longitude": lon,
                        "x_projected": round(x, 4),
                        "y_projected": round(y, 4),
                        "level": charger_type,
                        "plug_power_kw": plug_power,
                        "plug_count": dcfc_count,
                        "ev_network": network,
                        "connector_types": connectors,
                        "facility_type": facility_type,
                    })

                    stats["dcfc_total"] += 1
                    stats[f"dcfc_{state}"] += 1

        # Print per-file stats
        print(f"  Total rows in CSV:         {file_stats['total']}")
        print(f"  Skipped (not ELEC):        {file_stats['skip_not_elec']}")
        print(f"  Skipped (status != E):     {file_stats['skip_status']}")
        print(f"  Skipped (not public):      {file_stats['skip_access']}")
        print(f"  Skipped (bad coords):      {file_stats['skip_coords']}")
        print(f"  Skipped (Tesla Dest):      {file_stats['skip_tesla_dest']}")
        print(f"  Skipped (no L2/DCFC):      {file_stats['skip_no_ports']}")
        print(f"  Stations kept:             {file_stats['stations_kept']}")

    # 3. Write chargers.xml
    print(f"\n{'='*70}")
    print("Writing chargers.xml")
    print(f"{'='*70}")

    with open(OUTPUT_XML, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE chargers SYSTEM "chargers.dtd">\n')
        f.write('<chargers>\n')
        for c in all_chargers:
            f.write(
                f'    <charger id="{c["id"]}" '
                f'type="{c["type"]}" '
                f'plug_count="{c["plug_count"]}" '
                f'plug_power="{c["plug_power"]}" '
                f'x="{c["x"]:.4f}" '
                f'y="{c["y"]:.4f}"/>\n'
            )
        f.write('</chargers>\n')

    print(f"  Written {len(all_chargers)} charger entries to {OUTPUT_XML}")

    # 4. Write metadata CSV
    csv_fields = [
        "charger_id", "station_name", "address", "city", "state",
        "latitude", "longitude", "x_projected", "y_projected",
        "level", "plug_power_kw", "plug_count", "ev_network",
        "connector_types", "facility_type",
    ]
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(metadata_rows)

    print(f"  Written {len(metadata_rows)} rows to {OUTPUT_CSV}")

    # 5. Summary statistics
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"  Network CRS:     {network_crs}")
    print(f"  Total charger entries: {len(all_chargers)}")
    print(f"  L2 chargers:     {stats['l2_total']}")
    print(f"  DCFC chargers:   {stats['dcfc_total']}")
    print()

    # By state
    states_seen = sorted(set(r["state"] for r in metadata_rows))
    for st in states_seen:
        print(f"  {st}:  L2={stats.get(f'l2_{st}', 0)},  DCFC={stats.get(f'dcfc_{st}', 0)}")

    # Spatial extent (in WGS84 for readability)
    if metadata_rows:
        lats = [r["latitude"] for r in metadata_rows]
        lons = [r["longitude"] for r in metadata_rows]
        print(f"\n  Spatial extent (WGS84):")
        print(f"    Latitude:  {min(lats):.6f} to {max(lats):.6f}")
        print(f"    Longitude: {min(lons):.6f} to {max(lons):.6f}")

        xs = [r["x_projected"] for r in metadata_rows]
        ys = [r["y_projected"] for r in metadata_rows]
        print(f"  Spatial extent (projected, {network_crs}):")
        print(f"    X: {min(xs):.2f} to {max(xs):.2f}")
        print(f"    Y: {min(ys):.2f} to {max(ys):.2f}")

    # Charger type breakdown
    type_counts = defaultdict(int)
    for c in all_chargers:
        type_counts[c["type"]] += 1
    print(f"\n  By charger type:")
    for t in sorted(type_counts):
        print(f"    {t}: {type_counts[t]}")

    # Network breakdown
    net_counts = defaultdict(int)
    for r in metadata_rows:
        net_counts[r["ev_network"] or "(Non-Networked)"] += 1
    print(f"\n  By EV network (top 10):")
    for net, cnt in sorted(net_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {net}: {cnt}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()
