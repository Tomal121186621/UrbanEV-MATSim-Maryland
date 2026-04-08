#!/usr/bin/env python3
"""
Comprehensive diagnosis of UrbanEV simulation from iteration events file.
Analyzes charging behavior, charger utilization, SoC distribution, equity,
and en-route charging realism.

Usage: python diagnose_iteration.py <events.xml.gz> [<log_file>]
"""
import gzip
import sys
import statistics
from collections import defaultdict

def parse_attr(line, attr):
    """Extract attribute value from XML line."""
    key = f'{attr}="'
    s = line.find(key)
    if s < 0: return None
    s += len(key)
    e = line.find('"', s)
    return line[s:e] if e > s else None

def main():
    events_file = sys.argv[1] if len(sys.argv) > 1 else None
    log_file = sys.argv[2] if len(sys.argv) > 2 else "full_simulation.log"

    if not events_file:
        print("Usage: python diagnose_iteration.py <events.xml.gz> [<log_file>]")
        return

    print(f"Parsing {events_file}...")

    # Counters
    charging_starts = defaultdict(int)     # actType -> count
    charging_fails = defaultdict(int)
    charger_type_sessions = defaultdict(int)  # home/work/public -> count
    charger_id_usage = defaultdict(int)    # chargerId -> count
    soc_at_charging = []                   # SoC when arriving at charging activity
    soc_all = []                           # All SoC values
    energy_charged_by_type = defaultdict(list)  # chargerType -> [kWh list]
    queue_waits = []
    walk_distances = []
    stuck_count = 0
    stuck_links = defaultdict(int)
    scoring_total = 0
    scoring_costonly = 0
    scoring_noncost = 0

    # Charger power tracking
    charger_power = defaultdict(list)  # chargerType -> [kW list]

    # Activity tracking
    act_starts = defaultdict(int)
    person_vehicles = {}  # personId -> vehicleId

    with gzip.open(events_file, 'rt') as f:
        for line in f:
            if 'stuckAndAbort' in line:
                stuck_count += 1
                link = parse_attr(line, 'link')
                if link: stuck_links[link] += 1

            elif 'type="scoring"' in line:
                scoring_total += 1
                soc = parse_attr(line, 'soc')
                cost_only = parse_attr(line, 'costOnly')
                act_type = parse_attr(line, 'activityType')
                walking = parse_attr(line, 'walkingDistance')
                energy = parse_attr(line, 'energyChargedKWh')
                charger_type = parse_attr(line, 'chargerType')
                charger_power_kw = parse_attr(line, 'chargerPowerKw')
                queue_wait = parse_attr(line, 'queueWaitSeconds')

                if soc:
                    soc_val = float(soc)
                    soc_all.append(soc_val)

                if cost_only == 'true':
                    scoring_costonly += 1
                    if energy and charger_type:
                        e = float(energy)
                        if e > 0:
                            energy_charged_by_type[charger_type].append(e)
                            charger_type_sessions[charger_type] += 1
                    if charger_power_kw and charger_type:
                        try:
                            charger_power[charger_type].append(float(charger_power_kw))
                        except: pass
                    if queue_wait:
                        try:
                            qw = float(queue_wait)
                            if qw > 0: queue_waits.append(qw)
                        except: pass
                else:
                    scoring_noncost += 1
                    if soc and act_type and 'charging' in (act_type or ''):
                        soc_at_charging.append(float(soc))
                    if walking:
                        try:
                            wd = float(walking)
                            if wd > 0: walk_distances.append(wd)
                        except: pass

            elif 'actstart' in line or 'actend' in line:
                act_type = parse_attr(line, 'type')
                if act_type:
                    if 'actstart' in line:
                        act_starts[act_type] += 1

    # ── REPORT ──
    print(f"\n{'='*70}")
    print(f"COMPREHENSIVE CHARGING BEHAVIOR DIAGNOSIS")
    print(f"{'='*70}")

    print(f"\n--- 1. OVERALL METRICS ---")
    print(f"Scoring events total: {scoring_total:,}")
    print(f"  Non-cost (behavioral): {scoring_noncost:,}")
    print(f"  Cost-only (monetary): {scoring_costonly:,}")
    print(f"Stuck agents: {stuck_count}")

    print(f"\n--- 2. CHARGING ACTIVITY STARTS ---")
    charging_acts = {k:v for k,v in act_starts.items() if 'charging' in k}
    for k, v in sorted(charging_acts.items(), key=lambda x:-x[1]):
        print(f"  {k:35s}: {v:>6,}")
    total_charging = sum(charging_acts.values())
    total_failed = sum(v for k,v in charging_acts.items() if 'failed' in k)
    total_success = total_charging - total_failed
    print(f"  TOTAL charging activities: {total_charging:,}")
    print(f"  Successful: {total_success:,} ({total_success/max(total_charging,1)*100:.1f}%)")
    print(f"  Failed (no charger): {total_failed:,} ({total_failed/max(total_charging,1)*100:.1f}%)")

    print(f"\n--- 3. CHARGER TYPE USAGE (from cost-only scoring events) ---")
    for ct, count in sorted(charger_type_sessions.items(), key=lambda x:-x[1]):
        energies = energy_charged_by_type[ct]
        avg_kwh = statistics.mean(energies) if energies else 0
        med_kwh = statistics.median(energies) if energies else 0
        powers = charger_power[ct]
        avg_kw = statistics.mean(powers) if powers else 0
        print(f"  {ct:10s}: {count:>6,} sessions | avg {avg_kwh:.1f} kWh | median {med_kwh:.1f} kWh | avg power {avg_kw:.1f} kW")

    print(f"\n--- 4. ENERGY CHARGED DISTRIBUTION ---")
    all_energy = []
    for energies in energy_charged_by_type.values():
        all_energy.extend(energies)
    if all_energy:
        print(f"  Total sessions: {len(all_energy):,}")
        print(f"  Mean: {statistics.mean(all_energy):.2f} kWh")
        print(f"  Median: {statistics.median(all_energy):.2f} kWh")
        print(f"  Std: {statistics.stdev(all_energy):.2f} kWh" if len(all_energy) > 1 else "")
        print(f"  Min: {min(all_energy):.2f}, Max: {max(all_energy):.2f} kWh")
        buckets = {'<1':0, '1-5':0, '5-10':0, '10-20':0, '20-40':0, '>40':0}
        for e in all_energy:
            if e < 1: buckets['<1'] += 1
            elif e < 5: buckets['1-5'] += 1
            elif e < 10: buckets['5-10'] += 1
            elif e < 20: buckets['10-20'] += 1
            elif e < 40: buckets['20-40'] += 1
            else: buckets['>40'] += 1
        for k, v in buckets.items():
            print(f"    {k:>6s} kWh: {v:>6,} ({v/len(all_energy)*100:.1f}%)")
    else:
        print("  No charging sessions with energy data")

    print(f"\n--- 5. SoC DISTRIBUTION (all scoring events) ---")
    if soc_all:
        buckets = {'0-5%':0, '5-10%':0, '10-15%':0, '15-20%':0, '20-30%':0, '30-50%':0, '50-70%':0, '70-100%':0}
        for s in soc_all:
            if s < 0.05: buckets['0-5%'] += 1
            elif s < 0.10: buckets['5-10%'] += 1
            elif s < 0.15: buckets['10-15%'] += 1
            elif s < 0.20: buckets['15-20%'] += 1
            elif s < 0.30: buckets['20-30%'] += 1
            elif s < 0.50: buckets['30-50%'] += 1
            elif s < 0.70: buckets['50-70%'] += 1
            else: buckets['70-100%'] += 1
        for k, v in buckets.items():
            print(f"    {k:>10s}: {v:>8,} ({v/len(soc_all)*100:.1f}%)")
        low = sum(1 for s in soc_all if s < 0.20)
        print(f"  Below 20%: {low:,} ({low/len(soc_all)*100:.1f}%)")

    print(f"\n--- 6. SoC AT CHARGING ACTIVITIES ---")
    if soc_at_charging:
        print(f"  Events: {len(soc_at_charging):,}")
        print(f"  Mean SoC: {statistics.mean(soc_at_charging):.3f}")
        print(f"  Median SoC: {statistics.median(soc_at_charging):.3f}")
        print(f"  Min SoC: {min(soc_at_charging):.3f}")
        below20 = sum(1 for s in soc_at_charging if s < 0.20)
        print(f"  Below 20%: {below20:,} ({below20/len(soc_at_charging)*100:.1f}%)")
    else:
        print("  No charging activity scoring events")

    print(f"\n--- 7. QUEUE WAIT TIMES ---")
    if queue_waits:
        print(f"  Events with wait: {len(queue_waits):,}")
        print(f"  Mean: {statistics.mean(queue_waits)/60:.1f} min")
        print(f"  Median: {statistics.median(queue_waits)/60:.1f} min")
        print(f"  Max: {max(queue_waits)/60:.1f} min")
    else:
        print("  No queue wait events recorded")

    print(f"\n--- 8. WALKING DISTANCES ---")
    if walk_distances:
        print(f"  Events with walking: {len(walk_distances):,}")
        print(f"  Mean: {statistics.mean(walk_distances):.0f} m")
        print(f"  Median: {statistics.median(walk_distances):.0f} m")
        print(f"  Max: {max(walk_distances):.0f} m")
    else:
        print("  No walking distance events")

    print(f"\n--- 9. TOP STUCK LINKS ---")
    if stuck_links:
        for link, count in sorted(stuck_links.items(), key=lambda x:-x[1])[:10]:
            print(f"  Link {link}: {count} stuck events")

    print(f"\n--- 10. ACTIVITY TYPE SUMMARY ---")
    for k, v in sorted(act_starts.items(), key=lambda x:-x[1])[:20]:
        print(f"  {k:35s}: {v:>8,}")

    print(f"\nDiagnosis complete.")

if __name__ == "__main__":
    main()
