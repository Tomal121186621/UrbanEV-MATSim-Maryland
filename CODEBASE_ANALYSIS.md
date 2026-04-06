# UrbanEV-v2 Codebase Analysis

Generated: 2026-04-04
Codebase: `UrbanEV-v2-master/` (85 Java files, 7 packages)

## 1. Project Build

- **MATSim version:** 12.0
- **Java:** 11 (enforcer allows 11-17)
- **Dependencies:** matsim:12.0, matsim-contrib:ev:12.0, matsim-contrib:dvrp:12.0
- **Entry point:** `se.got.GotEVMain.main()` (via maven-assembly-plugin jar-with-dependencies)
- **DTDs:** `scenarios/dtd/chargers.dtd` (id, x, y, plug_power, plug_count, type, allowed_vehicles), `vehicletypes.dtd` (name, consumption, max_charging_rate, mass, physics params)

## 2. Class Dependency Graph

```
GotEVMain
 ├── Config + UrbanEVConfigGroup + EvConfigGroup
 ├── Controler
 │    └── EvModule (AbstractModule)
 │         ├── MobsimScopeEventHandling (StartupListener, AfterMobsimListener)
 │         ├── ElectricFleetModule
 │         │    ├── ElectricFleetSpecification(Impl) → ElectricFleetReader
 │         │    ├── ElectricVehicleTypesReader → ElectricVehicleType(Impl)
 │         │    └── ElectricFleets → ElectricVehicle(Impl) → Battery(Impl)
 │         ├── ChargingInfrastructureModule
 │         │    ├── ChargingInfrastructureSpecification(Impl) → ChargerReader
 │         │    └── ChargingInfrastructures → Charger(Impl) → ChargerSpecification
 │         ├── ChargingModule
 │         │    ├── ChargingLogic.Factory → ChargingLogicImpl
 │         │    │    └── ChargeUpToMaxSocStrategy (ChargingStrategy)
 │         │    ├── ChargingPower.Factory → VariableSpeedCharging
 │         │    └── ChargingHandler (MobsimAfterSimStepListener)
 │         ├── DischargingModule
 │         │    ├── DriveDischargingHandler (LinkLeaveEventHandler)
 │         │    │    └── DriveEnergyConsumption (SimpleDrive / LTH / TypeSpecificOhdeSlask)
 │         │    └── AuxDischargingHandler (MobsimAfterSimStepListener)
 │         │         └── AuxEnergyConsumption (OhdeSlaskiAux)
 │         └── EvStatsModule
 │              ├── EvMobsimListener (MobsimListener)
 │              ├── ChargingBehaviorScoresCollector (ControlerListener)
 │              ├── ChargerPowerCollector (ChargingStart/EndEventHandler)
 │              ├── ChargerOccupancyHistoryCollector
 │              └── Various TimeProfileCollectorProviders
 │
 ├── VehicleChargingHandler (ActivityStart/End, PersonLeavesVehicle, ChargingEnd)
 │    └── SmartChargingScheduler → SmartChargingTouHelper → ChargingCostUtils
 ├── SmartChargingEngine (MobsimEngine, delegates tick to VehicleChargingHandler)
 ├── ChangeChargingBehaviourModule → ChangeChargingBehaviour (PlanStrategy)
 └── ScoringFunctionFactory → ChargingBehaviourScoring (ArbitraryEventScoring)
      └── ChargingBehaviourScoringParameters (from UrbanEVConfigGroup)
```

## 3. Event Flow (One QSim Iteration)

### Startup Phase
1. `MobsimScopeEventHandling.notifyStartup()` — sets rangeAnxietyThreshold per person, generates private home/work chargers, writes charger XML

### During QSim
2. Agent departs home → `DriveDischargingHandler.handleEvent(LinkLeaveEvent)` — drains battery per link
3. `AuxDischargingHandler.notifyMobsimAfterSimStep()` — drains aux power each timestep
4. Agent arrives at "home charging" activity → `VehicleChargingHandler.handleEvent(ActivityStartEvent)`
   - Finds best charger via `findBestCharger()` (distance, availability, type compatibility)
   - If smart charging enabled + home + person is aware → `SmartChargingTouHelper.computeOptimalStartTime()` → defer via `SmartChargingScheduler.schedule()`
   - Otherwise → `charger.getLogic().addVehicle()` immediately
   - Emits `ChargingBehaviourScoringEvent` (non-cost: SOC, walking distance, activity type)
5. `SmartChargingEngine.doSimStep()` → `VehicleChargingHandler.tick()` → `SmartChargingScheduler.processDueTasks()` — plugs in deferred vehicles when scheduled time arrives
6. `ChargingHandler.notifyMobsimAfterSimStep()` → `charger.getLogic().chargeVehicles()` — updates battery SOC at chargeTimeStep intervals
7. `ChargingLogicImpl.chargeVehicles()` — power × time → battery.changeSoc(); checks strategy completion → emits `ChargingEndEvent`
8. Agent ends charging activity → `VehicleChargingHandler.handleEvent(ActivityEndEvent)`
   - Calculates energyChargedKWh = (currentSOC - startSOC) × capacityKWh
   - Classifies charger type: "home"/"work"/"public"
   - Emits `ChargingBehaviourScoringEvent` with `costOnly=true` (pricing time, energy, charger type)
   - Removes vehicle from charger

### Scoring
9. `ChargingBehaviourScoring.handleEvent()` processes each `ChargingBehaviourScoringEvent`:
   - **Non-cost event:** range anxiety penalty, empty battery penalty, walking penalty, home charging bonus, SOC difference penalty
   - **Cost-only event:** `betaMoney × alphaScaleCost × energyKWh × unitPrice × touMultiplier`
   - ToU multiplier uses 15-min intervals via `ChargingCostUtils.getHourlyCostMultiplier()`

### Between Iterations
10. `ChangeChargingBehaviour` (Provider<PlanStrategy>) → `ExpBetaPlanSelector` + `ChangeChargingBehaviourModule`:
    - `handlePlan()`: 5 modification strategies weighted randomly:
      a. Add " charging" suffix to activity (enable charging at that location)
      b. Remove " charging" suffix (disable charging)
      c. Change charging location (Gaussian perturbation to find nearby alternative)
      d. Adjust activity end time (±maxTimeFlexibility seconds) to enable failed charging
      e. No change
    - Uses `maxNumberSimultaneousPlanChanges`, `timeAdjustmentProbability`, `maxTimeFlexibility` from config
11. `MobsimScopeEventHandling.notifyAfterMobsim()` — clears handlers; on final iteration updates initialSoc from SOC histogram

### SubPopulation Switching
12. `ChangeChargingBehaviourModule.handleEvent(ChargingBehaviourScoringEvent)` — classifies agents:
    - Empty battery (SOC <= 0) → always "criticalSOC"
    - Last activity + large SOC delta vs threshold → probabilistically "criticalSOC"
    - Otherwise → "nonCriticalSOC"
    - Sets person attribute `subpopulation` accordingly for next iteration's strategy selection

## 4. Guice Binding Map

### EvModule.install()
```
bind(MobsimScopeEventHandling.class).asEagerSingleton()
addControlerListenerBinding().to(MobsimScopeEventHandling.class)
install(ElectricFleetModule)
install(ChargingInfrastructureModule)
install(ChargingModule)
install(DischargingModule)
install(EvStatsModule)
```

### ElectricFleetModule.install()
```
bind(ElectricFleetSpecification.class).toInstance(fleetSpecification)  // eager singleton, loaded from XML
bind(ElectricFleet.class).toProvider(...)  // QSim scope, creates from spec+factories
```

### ChargingInfrastructureModule.install()
```
bind(ChargingInfrastructureSpecification.class).toInstance(spec)  // loaded from chargersFile XML
bind(ChargingInfrastructure.class).toProvider(...)  // QSim scope, ChargingInfrastructures.create()
```

### ChargingModule.install()
```
bind(ChargingLogic.Factory.class).toProvider(...)  // creates ChargingLogicImpl + ChargeUpToMaxSocStrategy(1.0)
bind(ChargingPower.Factory.class).toInstance(ev -> VariableSpeedCharging.createForMaxChargingRate(ev))
bind(ChargingHandler.class).asEagerSingleton()  // QSim component under EV_COMPONENT
```

### DischargingModule.install()
```
bind(DriveEnergyConsumption.Factory.class)  // VehicleTypeSpecificFactory or SimpleDriveEnergyConsumption
bind(AuxEnergyConsumption.Factory.class)    // OhdeSlaskiAuxEnergyConsumption.Factory
bind(DriveDischargingHandler.class).asEagerSingleton()  // QSim component
bind(AuxDischargingHandler.class).asEagerSingleton()    // QSim component
```

### EvStatsModule.install() (conditional on evCfg.getTimeProfiles())
```
bind(EvMobsimListener.class) → EV_COMPONENT
bind(ChargerPowerCollector.class).asEagerSingleton()
bind(ChargerOccupancyHistoryCollector.class).asEagerSingleton()
bind(AggregatedDailyDemandProfilePlotter.class) as IterationEndsListener
Providers for: SocHistogram, IndividualSoc, ChargerOccupancy, ChargerTypeOccupancy, XYData, VehicleTypeAggregatedSoc
```
**Note:** ChargingBehaviorScoresCollector is a **manual singleton** (getInstance()), NOT Guice-managed.

### GotEVMain.loadConfigAndRun() (direct bindings)
```
bind(VehicleChargingHandler.class).asEagerSingleton()  // QSim scope
bind(SmartChargingEngine.class).asEagerSingleton()     // QSim scope (if enabled)
addPlanStrategyBinding("ChangeChargingBehaviour").toProvider(ChangeChargingBehaviourModule.class)
setScoringFunctionFactory(... ChargingBehaviourScoring ...)
```

## 5. Config Parameter Gap List

**15 parameters in config.xml that DON'T exist in UrbanEVConfigGroup.java:**

| # | Parameter | Value | Purpose |
|---|-----------|-------|---------|
| 1 | `chargersFile` | path | Chargers XML path (currently in EvConfigGroup, not UrbanEV) |
| 2 | `electricVehiclesFile` | path | EV fleet XML path (currently in EvConfigGroup, not UrbanEV) |
| 3 | `usePersonLevelParams` | true | Enable per-agent heterogeneous params |
| 4 | `publicL1Cost` | 0.18 | L1 public charging $/kWh |
| 5 | `publicL2Cost` | 0.25 | L2 public charging $/kWh |
| 6 | `publicDCFCCost` | 0.48 | DCFC public charging $/kWh |
| 7 | `l2PowerThreshold` | 3.0 | kW threshold: below=L1, above=L2 |
| 8 | `dcfcPowerThreshold` | 50.0 | kW threshold: below=L2, above=DCFC |
| 9 | `baseValueOfTimeFactor` | 0.4 | VoT scaling factor |
| 10 | `queueAnnoyanceFactor` | 2.0 | Queue time disutility multiplier |
| 11 | `detourDisutilityPerHour` | -6.0 | Detour penalty utils/hour |
| 12 | `enableEnRouteCharging` | true | Enable en-route charging strategy |
| 13 | `enRouteSearchRadius` | 2000.0 | Search radius for en-route chargers (m) |
| 14 | `enRouteSafetyBuffer` | 0.10 | SOC safety margin for en-route |
| 15 | `socProblemThreshold` | 0.05 | SOC below which agent is in trouble |

**Additionally:** Existing `publicChargingCost` in Java needs to be replaced by the 3-tier split (L1/L2/DCFC) plus power thresholds.

**Also note:** `chargersFile` and `electricVehiclesFile` are currently read from MATSim's `EvConfigGroup`, not from `UrbanEVConfigGroup`. Our config puts them in `urban_ev` module which won't be read. Either move them to the `ev` module in config.xml, or add getters/setters in UrbanEVConfigGroup.

## 6. Files to Modify

### UrbanEVConfigGroup.java (~line 50-200)
- Add 15 new field declarations with defaults
- Add 15 @StringGetter/@StringSetter pairs
- Add validation in `logIfSuspicious()`
- Replace `publicChargingCost` with `publicL1Cost`, `publicL2Cost`, `publicDCFCCost`
- Add `l2PowerThreshold`, `dcfcPowerThreshold` fields

### ChargingBehaviourScoringParameters.java (~line 15-45)
- Add new fields: `publicL1Cost`, `publicL2Cost`, `publicDCFCCost`, `l2PowerThreshold`, `dcfcPowerThreshold`, `usePersonLevelParams`, `baseValueOfTimeFactor`, `queueAnnoyanceFactor`, `detourDisutilityPerHour`
- Update Builder to read new config params

### ChargingBehaviourScoring.java (~line 70-120, cost scoring section)
- Replace single `publicChargingCost` lookup with 3-tier power-based lookup
- Use `l2PowerThreshold` and `dcfcPowerThreshold` to classify charger power tier
- Add person-level betaMoney override when `usePersonLevelParams=true`
- Add VoT-based waiting/detour scoring

### VehicleChargingHandler.java (~line 130-180, handleEvent ActivityEndEvent)
- Pass charger plug power to scoring event for tier classification
- Add charger power to ChargingBehaviourScoringEvent

### ChargingBehaviourScoringEvent.java (~line 20-40)
- Add `chargerPowerKw` field for power-tier classification in scoring

### GotEVMain.java (~line 80-120)
- Add en-route charging strategy registration if `enableEnRouteCharging=true`
- Add criticalSOC subpopulation switching logic
- Read `usePersonLevelParams` to conditionally load per-agent attributes

### MobsimScopeEventHandling.java (~line 60-100, notifyStartup)
- Respect person-level `homeChargerPower` attribute already present
- Add subpopulation switching based on SOC after each iteration

## 7. Files to Create

### se.urbanEV.planning.InsertEnRouteCharging.java
- New PlanStrategy for en-route charging insertion
- Uses `enRouteSearchRadius`, `enRouteSafetyBuffer`, `socProblemThreshold`
- Finds chargers along planned route when projected SOC drops below threshold

### se.urbanEV.planning.InsertEnRouteChargingModule.java
- Guice Provider for InsertEnRouteCharging strategy
- Register with `addPlanStrategyBinding("InsertEnRouteCharging")`

## 8. Potential Conflicts & Risks

### Threading
- `MobsimScopeEventHandling` uses `ConcurrentLinkedQueue` for handlers — thread-safe
- `SmartChargingScheduler` uses `synchronized` methods — thread-safe
- `ChargingBehaviorScoresCollector` uses standard HashMap — **NOT thread-safe**, but accessed from scoring functions which run single-threaded per agent
- `parallelEventHandling.numberOfThreads` is forced to 1 in `GotEVMain.loadConfigAndRun()` — safe but limits performance

### Breaking Changes
- Replacing `publicChargingCost` with 3-tier costs will break backward compatibility
  - **Mitigation:** Keep `publicChargingCost` as fallback if L1/L2/DCFC are all 0 or unset
- `ChangeChargingBehaviour` PlanStrategy is registered in GotEVMain, not via a module
  - New `InsertEnRouteCharging` should follow same pattern
- `ChargeUpToMaxSocStrategy(charger, 1.0)` hardcodes max SOC = 100%
  - May need to be configurable for en-route charging (charge to 80% for speed)

### Charger Type Handling
- `ChargerSpecification.DEFAULT_CHARGER_TYPE = "default"` — single type
- `findBestCharger()` in VehicleChargingHandler checks type compatibility: `ev.getChargerTypes().contains(charger.getChargerType())`
- Our chargers.xml uses types: "L2", "DCFC", "DCFC_TESLA"
- **FIXED (P10):** electric_vehicles.xml now uses:
  - Tesla vehicles: `charger_types="L2,DCFC,DCFC_TESLA"` (60,217 vehicles)
  - Non-Tesla: `charger_types="L2,DCFC"` (56,017 vehicles)
- **REMAINING FIX NEEDED in Java:** `MobsimScopeEventHandling.addPrivateCharger()` (~line 145)
  creates private home/work ChargerSpecification with `DEFAULT_CHARGER_TYPE = "default"`.
  These private chargers won't match any vehicle's charger_types (L2/DCFC).
  **Required change:** Use `"L2"` for chargers with power >= l2PowerThreshold (3.0 kW),
  and `"L1"` for chargers below that threshold. The charger type should be derived from
  the person's `homeChargerPower` attribute:
  - homeChargerPower >= 3.0 kW → type = "L2"
  - homeChargerPower < 3.0 kW and > 0 → type = "L1" (need to add "L1" to vehicle charger_types too)
  - workChargerPower (always 7.2 kW) → type = "L2"
  Additionally, vehicle charger_types must include "L1" for all vehicles to match L1 home chargers.
  Updated charger_types should be: Tesla → "L1,L2,DCFC,DCFC_TESLA", non-Tesla → "L1,L2,DCFC"

### Unit Conventions
- Battery/energy internally in **Joules** (J)
- Charger plug power internally in **Watts** (W)
- XML I/O converts kW↔W and kWh↔J
- Config values like `defaultHomeChargerPower` are in **kW** but `MobsimScopeEventHandling.addPrivateCharger()` converts kW→W
- Scoring uses kWh for cost calculation

### SubPopulation Architecture
- All agents start as "nonCriticalSOC" (set in GotEVMain)
- Config has strategies for both "nonCriticalSOC" and "criticalSOC"
- **No mechanism exists** to switch agents between subpopulations
- Need to add iteration-end logic to classify agents by end-of-day SOC

### Config File Path Issue
- `chargersFile` and `electricVehiclesFile` in our config are under `<module name="urban_ev">` but Java reads them from `<module name="ev">` (EvConfigGroup)
- **Fix:** Move these params to `<module name="ev">` in config.xml, OR add redundant readers in UrbanEVConfigGroup
