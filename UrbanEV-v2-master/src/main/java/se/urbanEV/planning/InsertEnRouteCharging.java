package se.urbanEV.planning;

import se.urbanEV.fleet.ElectricFleetSpecification;
import se.urbanEV.infrastructure.ChargingInfrastructureSpecification;
import org.matsim.api.core.v01.Scenario;
import org.matsim.core.api.experimental.events.EventsManager;
import org.matsim.core.replanning.PlanStrategy;
import org.matsim.core.replanning.PlanStrategyImpl;
import org.matsim.core.replanning.selectors.ExpBetaPlanSelector;

import javax.inject.Inject;
import javax.inject.Provider;

/**
 * Guice {@link Provider} for the {@code InsertEnRouteCharging} plan strategy.
 *
 * <p>Follows the same pattern as {@link ChangeChargingBehaviour}:
 * <ul>
 *   <li>Constructor injects {@link EventsManager}, {@link Scenario}, and
 *       {@link ChargingInfrastructure}.</li>
 *   <li>{@link #get()} creates a {@link PlanStrategyImpl} with
 *       {@link ExpBetaPlanSelector} as the base selector, so the module always
 *       operates on a score-weighted plan.</li>
 *   <li>The {@link InsertEnRouteChargingModule} is registered as an event handler
 *       with the {@link EventsManager} so it receives {@code ChargingBehaviourScoringEvent}s
 *       during the mobsim (via delegation to {@link SocProblemCollector}).</li>
 * </ul>
 *
 * <p>Registered in {@code GotEVMain} as {@code "InsertEnRouteCharging"} when
 * {@code urban_ev.enableEnRouteCharging=true}.  Add the following to {@code config.xml}
 * to activate it for the {@code criticalSOC} subpopulation:
 * <pre>{@code
 * <!-- strategy module — criticalSOC subpopulation -->
 * <parameterset type="strategysettings">
 *     <param name="strategyName"  value="InsertEnRouteCharging"/>
 *     <param name="weight"        value="0.2"/>
 *     <param name="subpopulation" value="criticalSOC"/>
 * </parameterset>
 *
 * <!-- optional: also apply to nonCriticalSOC at lower weight -->
 * <parameterset type="strategysettings">
 *     <param name="strategyName"  value="InsertEnRouteCharging"/>
 *     <param name="weight"        value="0.05"/>
 *     <param name="subpopulation" value="nonCriticalSOC"/>
 * </parameterset>
 * }</pre>
 */
public class InsertEnRouteCharging implements Provider<PlanStrategy> {

    private final EventsManager eventsManager;
    private final Scenario scenario;
    private final ChargingInfrastructureSpecification chargingInfrastructure;
    private final ElectricFleetSpecification electricFleetSpec;

    @Inject
    public InsertEnRouteCharging(EventsManager eventsManager,
                                 Scenario scenario,
                                 ChargingInfrastructureSpecification chargingInfrastructure,
                                 ElectricFleetSpecification electricFleetSpec) {
        this.eventsManager          = eventsManager;
        this.scenario               = scenario;
        this.chargingInfrastructure = chargingInfrastructure;
        this.electricFleetSpec      = electricFleetSpec;
    }

    @Override
    public PlanStrategy get() {
        double logitScaleFactor = 1.0;
        PlanStrategyImpl.Builder builder =
                new PlanStrategyImpl.Builder(new ExpBetaPlanSelector<>(logitScaleFactor));

        InsertEnRouteChargingModule module =
                new InsertEnRouteChargingModule(scenario, chargingInfrastructure, electricFleetSpec);

        builder.addStrategyModule(module);

        // Register the module as an event handler so it forwards ChargingBehaviourScoringEvents
        // to SocProblemCollector during the mobsim — mirrors ChangeChargingBehaviour pattern.
        eventsManager.addHandler(module);

        return builder.build();
    }
}
