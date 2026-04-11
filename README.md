# UrbanEV-MATSim-Maryland

Agent-based electric vehicle charging simulation for Maryland + DC using MATSim with the UrbanEV-v2 extension.

## Overview

This project simulates ~130K EV agents across the Maryland + DC road network (9.8M links) to study charging infrastructure utilization, range anxiety, energy demand, and equity. It includes both a **baseline** (original UrbanEV-v2) and an **enhanced** model with additional features for realistic EV charging behavior.

## Repository Structure

```
UrbanEV-MATSim-Maryland/
├── input/                          # Shared input files (network, plans, vehicles, chargers)
│   ├── maryland-dc-ev-network.xml.gz   # 4.9M node, 9.8M link road network (EPSG:26985)
│   ├── plans_maryland_ev.xml.gz        # ~130K EV agent 2-day plans
│   ├── electric_vehicles.xml           # EV fleet specifications (battery, SoC)
│   ├── vehicletypes.xml                # 35+ vehicle type specs (MATSim format)
│   ├── urbanev_vehicletypes.xml        # UrbanEV format vehicle types (kWh/100km)
│   ├── chargers.xml                    # 1,958 public charger locations (L2 + DCFC)
│   ├── through_stations.csv            # 14 highway boundary crossings
│   └── convert_*.py                    # Data conversion scripts
│
├── baseline_model/                 # Original UrbanEV-v2 (Parishwad et al. 2026)
│   ├── config_baseline.xml             # Baseline config (no en-route, no PHEV)
│   ├── src/                            # Original Java source code
│   ├── pom.xml                         # Maven build file
│   └── README.md                       # Original UrbanEV-v2 documentation
│
├── enhanced_model/                 # Enhanced framework (our contribution)
│   ├── config_enhanced.xml             # Enhanced config (all features enabled)
│   ├── src/                            # Modified Java source code
│   ├── pom.xml                         # Maven build file
│   └── README.md                       # UrbanEV-v2 documentation
│
├── output_baseline/                # Baseline simulation output
├── output_enhanced/                # Enhanced simulation output
│
├── validation/                     # Validation data and scripts
│   ├── ground_truth_benchmarks.csv     # 35 metrics from INL, NREL, DOE
│   ├── maryland_ev_registrations.csv   # MDOT EV registration data
│   ├── validate_simulation.py          # Automated validation script
│   └── analyze_equity_corridors.py     # Equity and corridor analysis
│
├── scenarios/                      # Scenario testing configs (future use)
│
├── run_baseline.sh                 # Run baseline simulation
├── run_enhanced.sh                 # Run enhanced simulation
└── CLAUDE.md                       # Development context and conventions
```

## Baseline vs Enhanced Model

| Feature | Baseline | Enhanced |
|---|:---:|:---:|
| Charging cost scoring | Yes | Yes |
| ChangeChargingBehaviour strategy | Yes | Yes |
| SelectExpBeta plan selection | Yes | Yes |
| Smart charging (ToU) | Yes | Yes |
| Queue traffic dynamics | Yes | Yes |
| FastAStarLandmarks routing | Yes | Yes |
| **En-route charging** | No | Yes |
| **PHEV gas fallback (CD/CS)** | No | Yes |
| **Multi-day SoC persistence** | No | Yes |
| **Workplace charger competition** | No | Yes |
| **Charger reliability/downtime** | No | Yes |
| **Charypar-Nagel + EV scoring** | No | Yes |
| **Income-sensitive betaMoney** | Linear | Sqrt elasticity |

### Baseline Scoring (8 components)
Range anxiety, empty battery, walking distance, home charging bonus, energy balance, charging cost, detour time, queue wait.

### Enhanced Scoring (9 components + Charypar-Nagel)
All baseline components + gasoline cost (PHEV) + full Charypar-Nagel (activity utility, travel disutility, late arrival penalty, monetary cost, stuck penalty).

## Quick Start

### Prerequisites
- Java 11+ (tested with JDK 23)
- Maven 3.6+
- 64+ GB RAM recommended

### Build and Run

```bash
# Run baseline
bash run_baseline.sh

# Run enhanced
bash run_enhanced.sh
```

### Validate Output
```bash
python validation/validate_simulation.py --output-dir output_enhanced/
```

## Data Sources

- **Road Network**: OpenStreetMap via MATSim network converter
- **Synthetic Population**: BMC Regional Travel Survey (v3), 6.6M persons
- **Charger Locations**: AFDC Alternative Fuel Stations (March 2026), MD + DC
- **EV Registrations**: MDOT Open Data Portal
- **Validation Benchmarks**: Idaho National Laboratory, NREL, DOE

## Coordinate System

All spatial data uses **EPSG:26985** (NAD83 / Maryland State Plane).

## Key References

- Parishwad, O., Gao, K., Najafi, A. (2026). *Integrated and Agent-Based Charging Demand Prediction Considering Cost-Aware and Adaptive Charging Behavior*. Transportation Research Part D, 154, 105285.
- Kickhofer, B., Nagel, K., Hoyer, K. (2011). *Enriching MATSim with Income-Dependent Marginal Utility of Money*. TRB Annual Meeting.
- Axsen, J., Plotter, S., Wolinetz, M. (2020). *Crafting Strong, Integrated Policy Mixes for Deep CO2 Mitigation*. Nature Climate Change.
- Wood, E., Rames, C., Muratori, M. (2018). *New EVSE Analytical Tools/Models*. NREL Technical Report.

## License

See `baseline_model/LICENSE` for the original UrbanEV-v2 license (GPL v2).
