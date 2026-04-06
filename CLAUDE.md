# UrbanEV-v2: MATSim EV Simulation for Maryland + DC

## Project Overview

Agent-based electric vehicle simulation using MATSim with the UrbanEV-v2 extension.
Simulates 362,374 EV agents (255K BEV + 107K PHEV) across the Maryland + DC road
network to study charging infrastructure utilization, range anxiety, and energy demand.

## Quick Start (Run on Any PC)

### Prerequisites
- **JDK 17** (Oracle or OpenJDK)
- **Maven 3.9+** (or install: download from archive.apache.org)
- **Python 3.8+** with csv/gzip modules (standard library only for conversion)
- **Git LFS** (for large network/plans files)
- **RAM:** minimum 64 GB recommended, 128 GB ideal

### Step 1: Clone & Pull LFS
```bash
git lfs install
git clone https://github.com/Tomal121186621/UrbanEV-MATSim-Maryland.git
cd UrbanEV-MATSim-Maryland
git lfs pull
```

### Step 2: Build the JAR
```bash
cd UrbanEV-v2-master
mvn clean package -DskipTests -Denforcer.skip=true
cd ..
```

### Step 3: Generate Input Files (if starting from raw CSV)
Place `synthetic_bmc_v3_with_coords.csv` (4.93 GB, not in repo) in `Input Files/`.
```bash
python "Input Files/convert_synpop_v3_to_matsim.py"
```
This generates: plans_maryland_ev.xml.gz, electric_vehicles.xml, vehicletypes.xml, ev_population_summary.csv.
Pre-generated versions of these files are already in the repo.

### Step 4: Run Simulation
```bash
bash run_full_simulation.sh [--skip-build]
```
Or manually:
```bash
java -Xmx96g -Xms16g -XX:+UseG1GC \
    --add-opens java.base/java.lang=ALL-UNNAMED \
    --add-opens java.base/java.util=ALL-UNNAMED \
    --add-opens java.base/java.lang.invoke=ALL-UNNAMED \
    -cp UrbanEV-v2-master/target/urban_ev-0.1-jar-with-dependencies.jar \
    se.got.GotEVMain scenarios/maryland/config.xml 0
```
Adjust `-Xmx` based on available RAM (minimum 64g for 362K agents on 9.8M link network).

## Coordinate Reference System

**All spatial data uses EPSG:26985 (NAD83 / Maryland State Plane).**
The MATSim network, charger locations, agent coordinates, and through stations are
all in this CRS. AFDC charger data (WGS84) is transformed during conversion.

## Directory Structure

```
UrbanEV-MATSim-Maryland-main/
├── CLAUDE.md                              # This file
├── CODEBASE_ANALYSIS.md                   # Full Java architecture analysis
├── UrbanEV_Pipeline_Diagram.png           # Visual pipeline diagram
├── GenerateDiagram.java                   # Regenerates pipeline diagram
├── RTS_Public_File_data_dictionary.xlsx   # Official RTS codebook
├── run_full_simulation.sh                 # One-command simulation runner
├── run_integration_test.sh                # Integration test runner
├── analyze_equity_corridors.py            # Post-processing analysis
├── generate_docs.py                       # Regenerates prompt_log + pipeline PDFs
├── generate_test_scenario.py              # Generates test scenario XMLs
├── validate_test_output.py                # Test output assertions
├── scenarios/maryland/
│   └── config.xml                         # MATSim config (10 iter test / 60 production)
├── Input Files/
│   ├── synthetic_bmc_v3_with_coords.csv   # 4.93 GB (NOT in repo — too large)
│   ├── convert_synpop_v3_to_matsim.py     # v3 CSV → MATSim XMLs (BEV+PHEV)
│   ├── convert_afdc_to_chargers_xml.py    # AFDC CSV → chargers.xml
│   ├── convert_synpop_to_matsim.py        # Legacy v1 converter (116K agents)
│   ├── maryland-dc-ev-network.xml.gz      # 284 MB road network (Git LFS)
│   ├── plans_maryland_ev.xml.gz           # 362,374 agent plans (Git LFS)
│   ├── electric_vehicles.xml              # 362,374 EV definitions
│   ├── vehicletypes.xml                   # 33 EV types + default "car"
│   ├── urbanev_vehicletypes.xml           # 49 types (Sweden format for UrbanEV)
│   ├── chargers.xml                       # 1,958 charger locations
│   ├── chargers_metadata.csv              # Charger details
│   ├── through_stations.csv               # 14 highway boundary crossings
│   └── ev_population_summary.csv          # Per-agent attribute summary
├── UrbanEV-v2-master/                     # Java source (MATSim + UrbanEV modules)
│   ├── pom.xml                            # Maven build (MATSim 12.0, JDK 11-17)
│   └── src/main/java/se/
│       ├── got/GotEVMain.java             # Entry point
│       └── urbanEV/                       # Charging, scoring, planning modules
└── test_scenario/                         # 50-agent integration test
```

## Key Data Facts

### Synthetic Population CSV (v3) — 4.93 GB
- **NOT in repo** (too large for Git/LFS). Must be placed manually.
- 19,936,981 rows, 53 columns, 6,076,834 unique persons.
- EV agents filtered by `has_ev=1` (362,374 persons, 1,183,157 trips).
- Coordinates already in EPSG:26985 — no transformation needed.
- Person ID constructed as `household_id + "_" + person_slot`.
- Time format: integer HHMM (e.g., 1430 = 14:30).
- All coordinates are non-zero (no through-station snapping needed for v3 data).

### Column Differences: v3 vs v1
| Field | v1 (old) | v3 (current) |
|---|---|---|
| EV filter | `assigned_ev=1` | `has_ev=1` |
| Person ID | `person_id` column | `household_id` + `person_slot` |
| EV model | `ev_make`, `ev_model` | `ev1_make`, `ev1_model`, `ev1_type` |
| Age | `age` (integer) | `age_group` (1-13 categorical) |
| Work charger | `charge_at_work_dummy` | `j1_benefits_ev_charging` |
| Trip number | `tripno` | `subtour_tripno` |
| Origin FIPS | `o_state_county_fips` | not present (use `home_state_county_fips`) |
| Battery | not in CSV | `ev1_battery_kwh` (used when >5 kWh) |

### Column Code Mappings (from RTS codebook)

**o_activity / d_activity:**
1=Home, 2=Work, 3=Volunteer, 4=School, 5=Shopping, 6=Meal(quick),
7=Meal, 8=Gas, 9=Healthcare, 10=Errand, 11=Socialize, 12=Civic/Religious,
13=Exercise, 14=Recreation, 15=Entertainment, 16=Drop-off/Pick-up, 18=Other.
MATSim mapping: 1→"home", 2→"work", 4→"school", all others→"other".

**travel_mode:**
1=Walk, 2=Bike, 3=Motorcycle, 4=Auto(driver), 5=Auto(passenger),
6=SchoolBus, 7=Rail, 8=Bus, 9=PrivateBus, 10=Paratransit,
11=Taxi, 12=Uber/Lyft, 13=Air, 14=Water, 15=Other.
MATSim mapping: 4→"car", all others→"walk" (teleported).

**age_group (RTS 13-group):**
1=Under5, 2=5-11, 3=12-13, 4=14-15, 5=16-17, 6=18-24,
7=25-34, 8=35-44, 9=45-54, 10=55-64, 11=65-74, 12=75-84, 13=85+.
Midpoints used: [3, 8, 13, 15, 17, 21, 30, 40, 50, 60, 70, 80, 88].

**hh_income_detailed (MPO 10-bracket, 0-indexed):**
0=<$10K, 1=$10-15K, 2=$15-25K, 3=$25-35K, 4=$35-50K,
5=$50-75K, 6=$75-100K, 7=$100-150K, 8=$150-200K, 9=$200K+.
Midpoints: [7500, 12500, 20000, 30000, 42500, 62500, 87500, 125000, 175000, 250000].

**home_type:** 0=Missing, 1=SFD, 2=SFA/townhouse, 3=2-9 unit apt,
4=10-49 unit apt, 5=50+ unit apt, 6=Mobile home.

**home_ownership:** 0=Missing, 1=Own/mortgage, 2=Rent, 3=Job/military, 4=Family/friend.

### MATSim Network
- 4,909,987 nodes, 9,831,519 links (OSM-derived).
- 85% of links are service/slow roads (<30 km/h) — footpaths, driveways.
- Bounding box: X 183,658–570,205, Y 32,787–249,470 (EPSG:26985).

### Chargers
- 1,958 entries: 1,607 L2 + 283 DCFC + 68 DCFC_TESLA.
- Top networks: ChargePoint (737), Blink (425), SWTCH (343).
- Power: L2=7.2kW, DCFC varies by network (50–150kW).

### Through Stations
- 14 highway boundary crossings for external trip resolution.
- State coverage: VA(51), PA(42), DE(10), WV(54), NJ(34), NY(36), DC(11).
- v3 dataset has all coords populated — through stations used only as fallback
  for coords outside network bounding box.

## EV Agent Population Profile (v3 Dataset)

| Metric | Value |
|---|---|
| Total EV agents | 362,374 |
| BEV agents | 255,235 (70.4%) |
| PHEV agents | 107,139 (29.6%) |
| Total trips | 1,183,157 |
| Internal (I-I) trips | 1,183,157 (100%) |
| Top model: Tesla Model Y | 61,981 (17.1%) |
| Home L2 charger (7.2kW) | 232,214 (64.1%) |
| Home L1 charger (1.4kW) | 76,706 (21.2%) |
| No home charger | 53,454 (14.7%) |
| Vehicle types | 33 (BEV + PHEV) |

## UrbanEV Simulation Architecture

### How It Works (Co-evolutionary Learning Loop)
Each iteration: Simulate → Score → Replan → Select Best → Repeat.
Agents learn optimal charging strategies over 60 iterations.

### Three Strategy Modules
1. **ChangeChargingBehaviour** — Add/remove/move charging at destinations the agent
   already visits (e.g., "charge at work instead of shopping"). No route change.
2. **InsertEnRouteCharging** — Add a new charging stop mid-trip for agents who ran
   out of battery. Splits a car leg into [drive→charge→drive]. Route changes.
   Charger selected based on agent's riskAttitude (averse=early, neutral=middle, seeking=late).
3. **SelectExpBeta** (MATSim built-in) — Probabilistically keep the best-scoring plan.

### Strategy Weights by Subpopulation
- **nonCriticalSOC:** SelectExpBeta 0.6, ChangeCharging 0.2, InsertEnRoute 0.2
- **criticalSOC:** ChangeCharging 0.4, InsertEnRoute 0.6

### Eight Scoring Components
| Component | Utility | What it penalizes/rewards |
|---|---|---|
| RANGE_ANXIETY | -6 | SoC below personal threshold |
| EMPTY_BATTERY | -15 | Battery reaches 0% |
| WALKING_DISTANCE | -1 | Walking from parking to charger |
| HOME_CHARGING | +1 | Charging at home (reward) |
| ENERGY_BALANCE | -4 | End-of-day SoC < start-of-day |
| CHARGING_COST | betaMoney × cost | Energy cost (MD rates: home $0.13, L2 $0.25, DCFC $0.48/kWh) |
| DETOUR_TIME | -6/hr + VoT | Extra driving to reach en-route charger |
| QUEUE_WAIT | VoT × 2.0 | Waiting for a free plug |

### Agent Heterogeneity
- **betaMoney:** f(income) — low income = very price-sensitive
- **valueOfTime:** f(income, employment) — non-workers get 0.6x reduction
- **rangeAnxietyThreshold:** f(income, age) — elderly/low-income more anxious [0.10-0.40]
- **riskAttitude:** neutral (high income, young) / moderate / averse (low income or elderly)
- **smartChargingAware:** 30% base probability, modified by income/age

## Derived Attribute Rules

**homeChargerPower (kW):**
- SFD + own + income>=6: 7.2
- SFD + own + income 4-5: 60%→7.2, 40%→1.4
- SFD + own + income<4: 1.4
- SFD + rent + income>=5: 1.4, else 0
- SFA + own + income>=5: 1.4, else 0
- Apartments: 0
- Mobile + own: 1.4

**betaMoney:** `-6.0 * (62500 / income_midpoint)`
**valueOfTime:** `(income/2080) * 0.5`, reduced by 0.6x for non-workers.

## Scripts

### convert_synpop_v3_to_matsim.py (PRIMARY)
Streams v3 CSV → plans.xml.gz + electric_vehicles.xml + vehicletypes.xml + summary.csv.
Handles both BEV and PHEV. Uses `ev1_battery_kwh` from CSV when available.
Run: `python "Input Files/convert_synpop_v3_to_matsim.py"` (~4.5 min)

### convert_afdc_to_chargers_xml.py
Reads AFDC CSVs → chargers.xml + chargers_metadata.csv.
Run: `python "Input Files/convert_afdc_to_chargers_xml.py"`

### convert_synpop_to_matsim.py (LEGACY)
Original converter for v1 dataset (116K agents). Kept for reference.

## MATSim Config (scenarios/maryland/config.xml)

- **14 modules:** global, network, plans, vehicles, ev, transit, controler, qsim,
  parallelEventHandling, planCalcScore, strategy, urban_ev, subtourModeChoice,
  TimeAllocationMutator
- **10 iterations** (test) / 60 (production — change `lastIteration`)
- **flowCapacityFactor=0.06**, storageCapacityFactor=0.18 (362K of ~6M pop)
- **QSim endTime=240:00:00** (10-day simulation window)
- **stuckTime=900** (15 min before removing stuck vehicles)
- **routingAlgorithmType=FastAStarLandmarks** (was Dijkstra — 100x faster)
- **global.numberOfThreads=14** (was 0 = single-threaded!)
- **2 subpopulations:** nonCriticalSOC, criticalSOC
- **Pricing (MD rates):** home $0.13/kWh, work free, L2 $0.25/kWh, DCFC $0.48/kWh
- Input file paths use `../../Input Files/` relative references from scenarios/maryland/

## Java Code Changes (from original UrbanEV-v2)

### GotEVMain.java
- **REMOVED** `config.parallelEventHandling().setNumberOfThreads(1)` — was forcing
  all event handling to single thread, killing performance.

### vehicletypes.xml
- **ADDED** default `"car"` vehicle type — required by MATSim's `PrepareForSimImpl`
  when `vehiclesSource=modeVehicleTypesFromVehiclesData`.

### urbanev_vehicletypes.xml
- **ADDED** 14 PHEV vehicle types + 2 generic fallbacks (bev, phev) to match
  all vehicle types in electric_vehicles.xml. Without these, `ElectricFleetReader`
  throws NPE at `ImmutableElectricVehicleSpecification:52`.

## Performance Notes

### Bottlenecks Found & Fixed
| Issue | Before | After | Speedup |
|---|---|---|---|
| Routing algorithm | Dijkstra (single-thread) | FastAStarLandmarks (14 threads) | ~100x |
| PrepareForSim | 6.5 sec/person | 0.17 sec/person | ~38x |
| Event handling | 1 thread (forced) | 14 threads (config) | ~14x |
| Stuck agents | 75% (300s stuck, 0.06 storage) | 53% (900s stuck, 0.18 storage) | improved |

### JVM Tuning (adjust for your hardware)
```
-Xmx96g              # max heap — use ~75% of physical RAM
-Xms16g              # initial heap — grows as needed
-XX:+UseG1GC         # best for large heaps
-XX:+AlwaysPreTouch  # pre-fault memory pages (avoid runtime page faults)
-XX:ParallelGCThreads=N  # set to ~cores-2
```

### Network Analysis
- 85% of 9.8M links are service/slow roads (<30 km/h)
- Only 2.8% are major roads (>=50 km/h)
- 97.7% are single-lane

## Charger Type Compatibility

All EVs and chargers must use matching type strings:
- **Vehicle charger_types:** Tesla → `L1,L2,DCFC,DCFC_TESLA`, non-Tesla → `L1,L2,DCFC`
- **Public chargers (chargers.xml):** types `L2`, `DCFC`, `DCFC_TESLA`
- **Private chargers (Java-generated):** `L1` (power < 3kW) or `L2` (power >= 3kW)

## Known Limitations
- PHEV gas fallback not modeled — UrbanEV treats all EVs as battery-only.
  PHEVs with small batteries (13-25 kWh) may run out quickly.
- Battery initial_soc randomized 40-80% — not calibrated to real data.
  PHEVs should ideally start at 70-95% since owners typically charge overnight.
- Home charger assignment uses probabilistic rules, not actual charger registry data.
- 53% stuck agent rate in first test run — needs further tuning or network simplification.
- `soc_histogram_time_profiles.txt` crash at final iteration — bug in
  `MobsimScopeEventHandling.notifyAfterMobsim()` trying to read a file not generated.

## Conventions
- Random seed: 42 (for reproducibility)
- All XML uses UTF-8 encoding
- Plans file is gzipped (compresslevel=6)
- Person IDs: `household_id + "_" + person_slot` (match across all output files)
- Vehicle type keys: lowercase, spaces→underscores (e.g., "model_y", "x5_xdrive50e")
