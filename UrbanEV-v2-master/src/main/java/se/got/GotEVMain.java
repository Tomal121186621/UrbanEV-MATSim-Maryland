package se.got;

import se.urbanEV.EvModule;
import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.planning.ChangeChargingBehaviour;
import se.urbanEV.planning.InsertEnRouteCharging;
import se.urbanEV.planning.SocProblemCollector;
import se.urbanEV.scoring.ChargingBehaviourScoring;
import se.urbanEV.scoring.ChargingBehaviourScoringParameters;
import org.apache.log4j.Logger;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.Population;
import org.matsim.contrib.ev.EvConfigGroup;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigGroup;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.controler.AbstractModule;
import org.matsim.core.controler.Controler;
import org.matsim.core.controler.events.IterationStartsEvent;
import org.matsim.core.controler.listener.IterationStartsListener;
import org.matsim.core.scenario.ScenarioUtils;
import org.matsim.core.scoring.ScoringFunction;
import org.matsim.core.scoring.ScoringFunctionFactory;
import org.matsim.core.scoring.SumScoringFunction;

import java.io.IOException;

/**
 * Entry point for the Maryland+DC UrbanEV-v2 simulation.
 *
 * <h3>Config.xml notes for en-route charging</h3>
 * When {@code urban_ev.enableEnRouteCharging=true}, add the following strategy
 * settings to your {@code config.xml} {@code strategy} module:
 *
 * <pre>{@code
 * <!-- criticalSOC subpopulation — primary target for en-route insertion -->
 * <parameterset type="strategysettings">
 *     <param name="strategyName"  value="InsertEnRouteCharging"/>
 *     <param name="weight"        value="0.2"/>
 *     <param name="subpopulation" value="criticalSOC"/>
 * </parameterset>
 *
 * <!-- nonCriticalSOC — lower weight for exploration -->
 * <parameterset type="strategysettings">
 *     <param name="strategyName"  value="InsertEnRouteCharging"/>
 *     <param name="weight"        value="0.05"/>
 *     <param name="subpopulation" value="nonCriticalSOC"/>
 * </parameterset>
 * }</pre>
 */
public class GotEVMain {

    private static final Logger log = Logger.getLogger(GotEVMain.class);
    private static final String SMART_CHARGING_COMPONENT = "SmartChargingEngine";

    public GotEVMain() {}

    // ─────────────────────────────────────────────────────────────────────────
    // main
    // ─────────────────────────────────────────────────────────────────────────

    public static void main(String[] args) throws IOException {
        String configPath    = "";
        int initIterations   = 20;

        if (args != null && args.length == 2) {
            configPath     = args[0];
            initIterations = Integer.parseInt(args[1]);
        } else if (args != null && args.length == 1) {
            configPath     = args[0];
            initIterations = 0;
        } else {
            System.out.println("Config file missing. Please supply a config file path as a program argument.");
            throw new IOException("Could not start simulation. Config file missing.");
        }

        log.info("Config file path: " + configPath);
        log.info("Number of iterations to initialize SOC distribution: " + initIterations);

        ConfigGroup[] configGroups = new ConfigGroup[]{ new EvConfigGroup(), new UrbanEVConfigGroup() };
        Config config = ConfigUtils.loadConfig(configPath, configGroups);

        if (initIterations > 0) {
            Config initConfig = ConfigUtils.loadConfig(configPath, configGroups);
            initConfig.controler().setLastIteration(initIterations);
            initConfig.controler().setOutputDirectory(
                    initConfig.controler().getOutputDirectory() + "/init");
            loadConfigAndRun(initConfig);

            EvConfigGroup evConfigGroup = (EvConfigGroup) config.getModules().get("ev");
            evConfigGroup.setVehiclesFile("output/init/output_evehicles.xml");
            config.controler().setOutputDirectory(
                    config.controler().getOutputDirectory() + "/train");
        }
        loadConfigAndRun(config);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // loadConfigAndRun
    // ─────────────────────────────────────────────────────────────────────────

    private static void loadConfigAndRun(Config config) {

        // Use config-specified thread count for parallel event handling (not forced to 1)
        final Scenario scenario = ScenarioUtils.loadScenario(config);
        Controler controler = new Controler(scenario);

        UrbanEVConfigGroup urbanEvCfg =
                (UrbanEVConfigGroup) controler.getConfig().getModules().get(UrbanEVConfigGroup.GROUP_NAME);
        if (urbanEvCfg != null) {
            urbanEvCfg.logIfSuspicious();
        }

        // ── EV module + QSim components ───────────────────────────────────────
        controler.addOverridingModule(new EvModule());
        controler.configureQSimComponents(components -> {
            components.addNamedComponent(EvModule.EV_COMPONENT);
            if (urbanEvCfg != null && urbanEvCfg.isEnableSmartCharging()) {
                components.addNamedComponent(SMART_CHARGING_COMPONENT);
            }
        });

        controler.addOverridingQSimModule(new org.matsim.core.mobsim.qsim.AbstractQSimModule() {
            @Override
            protected void configureQSim() {
                bind(se.urbanEV.charging.VehicleChargingHandler.class).asEagerSingleton();
                bind(se.urbanEV.charging.SmartChargingEngine.class).asEagerSingleton();
                addQSimComponentBinding(SMART_CHARGING_COMPONENT)
                        .to(se.urbanEV.charging.SmartChargingEngine.class);
            }
        });

        // ── A) Strategy bindings ──────────────────────────────────────────────
        // ChangeChargingBehaviour is always registered.
        // InsertEnRouteCharging is registered only when enableEnRouteCharging=true;
        // the config.xml strategy weights then control how often each subpopulation
        // uses it.  See class-level Javadoc for the required config.xml snippet.
        controler.addOverridingModule(new AbstractModule() {
            @Override
            public void install() {
                addPlanStrategyBinding("ChangeChargingBehaviour")
                        .toProvider(ChangeChargingBehaviour.class);

                if (urbanEvCfg != null && urbanEvCfg.isEnableEnRouteCharging()) {
                    addPlanStrategyBinding("InsertEnRouteCharging")
                            .toProvider(InsertEnRouteCharging.class);
                }
            }
        });

        // ── B) SocProblemCollector — register as persistent event handler ─────
        // The collector receives ChargingBehaviourScoringEvents throughout the mobsim
        // and makes previous-iteration SoC problems available to InsertEnRouteChargingModule
        // during replanning.  Its reset() is driven by the IterationStartsListener below.
        Population population = controler.getScenario().getPopulation();
        SocProblemCollector.initialize(population); // provide Population for threshold lookup

        controler.addOverridingModule(new AbstractModule() {
            @Override
            public void install() {
                // Registers the singleton with MATSim's event dispatch so it receives
                // ChargingBehaviourScoringEvents across all iterations.
                addEventHandlerBinding().toInstance(SocProblemCollector.getInstance());
            }
        });

        controler.addControlerListener(new IterationStartsListener() {
            @Override
            public void notifyIterationStarts(IterationStartsEvent event) {
                // Clear previous iteration's SoC problem records before each new mobsim.
                SocProblemCollector.getInstance().reset(event.getIteration());
                if (event.getIteration() > 0) {
                    log.info(String.format(
                            "SocProblemCollector: cleared records for iteration %d "
                            + "(previous iteration had %d affected persons)",
                            event.getIteration(),
                            SocProblemCollector.getInstance().getProblemPersonCount()));
                }
            }
        });

        // ── Charger reliability (Rempel et al. 2022, NREL) ─────────────────────
        // Randomly disables charger plugs per iteration to simulate real-world
        // downtime. Only active when enableChargerReliability=true in config.
        controler.addOverridingModule(new AbstractModule() {
            @Override
            public void install() {
                addControlerListenerBinding().to(se.urbanEV.charging.ChargerReliabilityManager.class);
            }
        });

        // ── Scoring function ──────────────────────────────────────────────────
        // Todo: replace with CharyparNagelScoringFunctionFactory when calibrated params available
        controler.setScoringFunctionFactory(new ScoringFunctionFactory() {
            @Override
            public ScoringFunction createNewScoringFunction(Person person) {
                ChargingBehaviourScoringParameters params =
                        new ChargingBehaviourScoringParameters.Builder(scenario).build();
                SumScoringFunction sum = new SumScoringFunction();
                sum.addScoringFunction(new ChargingBehaviourScoring(params, person));
                return sum;
            }
        });

        // ── C) Person attribute assignment ────────────────────────────────────
        // Pass 1: subpopulation + smart-charging awareness (uniform across all agents)
        double awareness = (urbanEvCfg != null) ? urbanEvCfg.getAwarenessFactor() : 0.0;
        java.util.Random rng = new java.util.Random(controler.getConfig().global().getRandomSeed());

        int awareCount = 0;
        int total      = 0;
        for (Person person : population.getPersons().values()) {
            // Subpopulation starts as nonCriticalSOC; ChangeChargingBehaviourModule
            // reclassifies agents to criticalSOC based on in-iteration SoC events.
            person.getAttributes().putAttribute("subpopulation", "nonCriticalSOC");

            boolean aware = rng.nextDouble() <= awareness;
            person.getAttributes().putAttribute("smartChargingAware", aware);
            total++;
            if (aware) awareCount++;
        }
        log.info(String.format(
                "Smart charging awareness assignment: %.1f%% configured → %d / %d persons marked smartChargingAware=true",
                awareness * 100.0, awareCount, total));

        // Pass 2: heterogeneous parameters when usePersonLevelParams=true
        // Income midpoints for hh_income_detailed 0-9 (MPO 10-bracket, 0-indexed, USD):
        //   0=<$10K  1=$10-15K  2=$15-25K  3=$25-35K  4=$35-50K
        //   5=$50-75K  6=$75-100K  7=$100-150K  8=$150-200K  9=$200K+
        final double[] incomeMidpoints = {
            7500, 12500, 20000, 30000, 42500, 62500, 87500, 125000, 175000, 250000
        };

        if (urbanEvCfg != null && urbanEvCfg.isUsePersonLevelParams()) {
            int betaCount  = 0;
            int votCount   = 0;

            for (Person person : population.getPersons().values()) {
                double midpoint = resolveIncomeMidpoint(person, incomeMidpoints);

                // betaMoney: -6.0 * (62500 / midpoint)
                // Keep existing attribute if already set (e.g. from preprocessing or prior run).
                if (person.getAttributes().getAttribute("betaMoney") == null) {
                    double betaMoney = -6.0 * (62500.0 / midpoint);
                    person.getAttributes().putAttribute("betaMoney", betaMoney);
                    betaCount++;
                }

                // valueOfTime: (income / 2080) * 0.5 [USD/hr]; non-workers × 0.6
                // Keep existing attribute if already set.
                if (person.getAttributes().getAttribute("valueOfTime") == null) {
                    double vot = (midpoint / 2080.0) * 0.5;
                    if (!isWorker(person)) vot *= 0.6;
                    person.getAttributes().putAttribute("valueOfTime", vot);
                    votCount++;
                }

                // rangeAnxietyThreshold is set by MobsimScopeEventHandling.notifyStartup()
                // if not already present — no action needed here.
            }

            log.info(String.format(
                    "usePersonLevelParams=true: assigned betaMoney for %d persons, "
                    + "valueOfTime for %d persons (out of %d total)",
                    betaCount, votCount, total));
        }

        controler.run();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Returns the income midpoint (USD) for the person's {@code hh_income_detailed}
     * attribute (0-indexed MPO 10-bracket).  Falls back to bracket 5 ($62,500 midpoint)
     * when the attribute is absent or unparseable.
     */
    private static double resolveIncomeMidpoint(Person person, double[] midpoints) {
        Object attr = person.getAttributes().getAttribute("hh_income_detailed");
        if (attr != null) {
            try {
                int idx = Integer.parseInt(attr.toString());
                if (idx >= 0 && idx < midpoints.length) return midpoints[idx];
            } catch (NumberFormatException ignored) { }
        }
        return midpoints[5]; // $62,500 — median bracket fallback
    }

    /**
     * Returns true when the person's {@code employment_status} attribute equals 0
     * (Worker).  Non-workers receive a 0.6× VoT reduction.
     * Employment codes: 0=Worker, 1=Retired, 2=Volunteer, 3=Homemaker,
     * 4=Unemployed(seeking), 5=Unemployed(not seeking), 6=Student,
     * 7=Disabled, 8=Child(synthetic), 9=N/A(synthetic).
     */
    private static boolean isWorker(Person person) {
        Object attr = person.getAttributes().getAttribute("employment_status");
        if (attr != null) {
            try { return Integer.parseInt(attr.toString()) == 0; }
            catch (NumberFormatException ignored) { }
        }
        return true; // assume worker when unknown (conservative — higher VoT)
    }
}
