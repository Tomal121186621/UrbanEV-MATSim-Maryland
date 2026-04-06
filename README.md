# UrbanEV-MATSim-Maryland

**Agent-based electric vehicle simulation for the Maryland + DC metropolitan region**

A MATSim-based simulation framework that models ~116,000 EV agents across the Maryland and DC road network to study charging infrastructure utilization, range anxiety behavior, and energy demand patterns. Built on the [UrbanEV-v2](https://github.com/CDAT-DVRP/UrbanEV-v2) extension for MATSim.

> **Raas Sarker Tomal**
> Graduate Research Assistant, [Maryland Transportation Institute](https://mti.umd.edu/), University of Maryland

---

## Overview

This project simulates realistic electric vehicle charging behavior at regional scale using activity-based travel demand from a synthetic population. It combines:

- **MATSim agent-based simulation** with 116,234 EV agents and 382,261 daily trips
- **UrbanEV-v2 framework** for EV-specific charging logic, battery discharge, and smart charging
- **Real-world charging infrastructure** — 1,958 charger locations from the AFDC database (L2 + DCFC)
- **Heterogeneous agent attributes** — income-based charging preferences, home charger access, range anxiety profiles, and value-of-time scoring

### Key Research Questions

- How does charging infrastructure placement affect equity across income groups?
- Where do EV drivers experience range anxiety, and which corridors are underserved?
- What is the aggregate energy demand profile from EV charging across the region?

## Simulation at a Glance

| Metric | Value |
|---|---|
| EV agents | 116,234 |
| Daily trips | 382,261 (98% internal) |
| Road network | 4.9M nodes, 9.8M links |
| Charger locations | 1,958 (L2 + DCFC) |
| Vehicle types | 35 (Tesla, Nissan, Ford, VW, etc.) |
| Simulation iterations | 60 |
| Coordinate system | EPSG:26985 (NAD83 / Maryland State Plane) |

### Agent Population Profile

| Category | Breakdown |
|---|---|
| Top model | Tesla Model Y (28.6%) |
| Home L2 charger (7.2 kW) | 35.1% |
| Home L1 charger (1.4 kW) | 33.6% |
| No home charger | 31.3% |
| Agents with external trips | 2.9% |

## Architecture

```
                    ┌──────────────────────────────┐
                    │   Synthetic Population CSV    │
                    │   (6.6 GB, ~6M persons)       │
                    └──────────────┬───────────────┘
                                   │ convert_synpop_to_matsim.py
                                   ▼
              ┌─────────────────────────────────────────┐
              │  MATSim Input Files                     │
              │  plans.xml.gz │ electric_vehicles.xml   │
              │  vehicletypes.xml │ chargers.xml        │
              │  network.xml.gz │ config.xml            │
              └─────────────────────┬───────────────────┘
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │  MATSim + UrbanEV-v2 Simulation Engine  │
              │  (Java, 60 iterations)                  │
              │                                         │
              │  • Activity-based demand                │
              │  • EV charging / discharging            │
              │  • Smart charging + TOU pricing         │
              │  • En-route charging strategy            │
              │  • Charging behavior scoring             │
              └─────────────────────┬───────────────────┘
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │  Post-Processing & Analysis             │
              │  analyze_equity_corridors.py            │
              │                                         │
              │  • Equity metrics by income group       │
              │  • Corridor SoC profiles                │
              │  • Charger utilization analysis          │
              └─────────────────────────────────────────┘
```

## Repository Structure

```
├── CLAUDE.md                          # Project documentation & conventions
├── CODEBASE_ANALYSIS.md               # Java architecture analysis
├── Input Files/
│   ├── convert_synpop_to_matsim.py    # Synthetic pop → MATSim XMLs
│   ├── convert_afdc_to_chargers_xml.py # AFDC CSV → chargers.xml
│   ├── plans_maryland_ev.xml.gz       # 116K agent daily plans
│   ├── electric_vehicles.xml          # EV definitions (battery, SoC)
│   ├── vehicletypes.xml              # 35 vehicle type specifications
│   ├── chargers.xml                   # 1,958 charger locations
│   ├── maryland-dc-ev-network.xml.gz  # Road network (Git LFS)
│   └── through_stations.csv           # 14 highway boundary crossings
├── UrbanEV-v2-master/                 # Java simulation framework
│   ├── src/main/java/se/urbanEV/     # Core EV modules
│   │   ├── charging/                  # Charging logic & smart charging
│   │   ├── discharging/              # Energy consumption models
│   │   ├── fleet/                     # EV fleet management
│   │   ├── infrastructure/           # Charger infrastructure
│   │   ├── planning/                 # Charging strategy planners
│   │   ├── scoring/                  # Charging behavior scoring
│   │   └── stats/                    # Statistics & visualization
│   └── scenarios/sweden/             # Original Swedish test scenarios
├── scenarios/maryland/
│   └── config.xml                    # MATSim config (13 modules, 38 EV params)
├── test_scenario/                    # Integration test (50 agents, 15 iterations)
├── analyze_equity_corridors.py       # Post-processing: equity + corridor analysis
├── generate_test_scenario.py         # Generates integration test XMLs
├── run_integration_test.sh           # End-to-end test pipeline
├── validate_test_output.py           # 8 behavioral assertions
└── run_full_simulation.sh            # Full Maryland simulation launcher
```

## Getting Started

### Prerequisites

- **Java** 11–17 (JDK 23 works with `--add-opens` flags; see CLAUDE.md)
- **Maven** 3.6+
- **Python** 3.8+ (for data conversion and analysis scripts)

### Build

```bash
cd UrbanEV-v2-master
mvn clean package -DskipTests
```

### Run Integration Test

A quick validation with 50 agents and 15 iterations:

```bash
bash run_integration_test.sh
```

All 8 behavioral assertions should pass. Use `--skip-build` to skip Maven rebuild.

### Run Full Simulation

```bash
bash run_full_simulation.sh
```

Runs 60 iterations with 116K agents on the full Maryland + DC network. Output goes to `scenarios/maryland/output/maryland_ev_enhanced/`.

### Post-Processing

```bash
python3 analyze_equity_corridors.py \
  --output-dir scenarios/maryland/output/maryland_ev_enhanced/
```

Generates equity analysis, corridor SoC profiles, and charger utilization reports.

## Data Sources

| Dataset | Source | Size |
|---|---|---|
| Synthetic population | MWCOG/BMC Regional Travel Survey | 6.6 GB (not in repo*) |
| Road network | OpenStreetMap (via MATSim) | 284 MB (Git LFS) |
| Charger locations | [AFDC](https://afdc.energy.gov/) (March 2026) | 704 KB |
| EV specifications | EPA, manufacturer data | 35 vehicle types |

*\*The 6.6 GB synthetic population CSV exceeds GitHub's 2 GB LFS limit and is excluded from the repository.*

## Simulation Configuration Highlights

- **Pricing:** Home $0.13/kWh, Work free, L2 $0.25/kWh, DCFC $0.48/kWh (Maryland rates)
- **Two subpopulations:** `nonCriticalSOC` (normal charging behavior) and `criticalSOC` (aggressive en-route charging)
- **Smart charging** with time-of-use awareness
- **Income-sensitive scoring** via `betaMoney = -6.0 × (62500 / income)`
- **Home charger assignment** based on housing type, ownership, and income bracket

## License

The UrbanEV-v2 framework is based on work from Chalmers University of Technology. See `UrbanEV-v2-master/LICENSE` for details.

## Acknowledgments

- [MATSim](https://www.matsim.org/) — Multi-Agent Transport Simulation
- [UrbanEV-v2](https://github.com/CDAT-DVRP/UrbanEV-v2) — EV extension for MATSim
- Maryland Transportation Institute, University of Maryland
- MWCOG/BMC for synthetic population data
- U.S. DOE Alternative Fuels Data Center for charger location data
