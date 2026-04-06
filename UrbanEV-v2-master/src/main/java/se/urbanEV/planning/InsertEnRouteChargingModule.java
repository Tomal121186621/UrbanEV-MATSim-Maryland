package se.urbanEV.planning;

import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.infrastructure.ChargerSpecification;
import se.urbanEV.infrastructure.ChargingInfrastructureSpecification;
import se.urbanEV.scoring.ChargingBehaviourScoringEvent;
import se.urbanEV.scoring.ChargingBehaviourScoringEventHandler;
import org.apache.log4j.Logger;
import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.network.Link;
import org.matsim.api.core.v01.network.Network;
import org.matsim.api.core.v01.population.*;
import org.matsim.api.core.v01.replanning.PlanStrategyModule;
import org.matsim.contrib.util.distance.DistanceUtils;
import org.matsim.core.population.routes.NetworkRoute;
import org.matsim.core.replanning.ReplanningContext;

import java.util.*;

/**
 * {@link PlanStrategyModule} that inserts an en-route public charging stop into
 * a plan for agents who experienced a SoC-below-threshold event in the previous
 * iteration (as recorded by {@link SocProblemCollector}).
 *
 * <h3>Pipeline per plan</h3>
 * <ol>
 *   <li>Check {@link SocProblemCollector}: if the agent had no SoC problems, return immediately.</li>
 *   <li>Read the agent's {@code riskAttitude} person attribute (default {@code "moderate"}).</li>
 *   <li>For each SoC problem record, locate the car leg in the plan that was active when
 *       the problem occurred.</li>
 *   <li>Enumerate charger candidates positioned along that leg's route, within
 *       {@code enRouteSearchRadius} metres of each sampled link.</li>
 *   <li>Select one candidate according to risk attitude (early/middle/late along route).</li>
 *   <li>Split the leg at the selected charger: insert a new {@code "other charging"} activity
 *       and two re-routeable legs in place of the original leg.</li>
 *   <li>At most one insertion is made per {@code handlePlan()} call.</li>
 * </ol>
 *
 * <h3>Charger duration heuristic</h3>
 * DCFC stations ({@code plugPower > dcfcPowerThreshold kW}): 30 min maximum duration.<br>
 * L2 stations: 60 min maximum duration.
 *
 * <h3>Duplicate-stop prevention</h3>
 * If the plan already contains a {@code " charging"} activity within
 * {@value #DEDUP_RADIUS_M} m of a candidate charger, that candidate is skipped.
 */
class InsertEnRouteChargingModule implements PlanStrategyModule, ChargingBehaviourScoringEventHandler {

    private static final Logger log = Logger.getLogger(InsertEnRouteChargingModule.class);

    private static final String CHARGING_IDENTIFIER      = " charging";

    /** Minimum route links required before insertion is attempted (very short legs are skipped). */
    private static final int MIN_ROUTE_LINKS = 5;

    /**
     * Sample stride for route-link scanning.  Every {@value #LINK_STRIDE}th link is tested
     * against the charger set to keep the O(links × chargers) cost acceptable on large networks.
     */
    private static final int LINK_STRIDE = 5;

    /** Radius within which an existing charging activity suppresses a new candidate (dedup). */
    private static final double DEDUP_RADIUS_M = 5_000.0;

    /** Maximum duration (seconds) for a DCFC en-route stop. */
    private static final double DCFC_STOP_DURATION_SEC = 1_800.0; // 30 min

    /** Maximum duration (seconds) for an L2 en-route stop. */
    private static final double L2_STOP_DURATION_SEC = 3_600.0; // 60 min

    private final Random random = org.matsim.core.gbl.MatsimRandom.getLocalInstance();
    private final Network network;
    private final ChargingInfrastructureSpecification chargingInfrastructure;
    private final PopulationFactory popFactory;
    private final double enRouteSearchRadius;
    private final double dcfcPowerThresholdKw;

    InsertEnRouteChargingModule(Scenario scenario, ChargingInfrastructureSpecification chargingInfrastructure) {
        this.network = scenario.getNetwork();
        this.chargingInfrastructure = chargingInfrastructure;
        this.popFactory = scenario.getPopulation().getFactory();

        UrbanEVConfigGroup evCfg = (UrbanEVConfigGroup)
                scenario.getConfig().getModules().get(UrbanEVConfigGroup.GROUP_NAME);
        this.enRouteSearchRadius  = (evCfg != null) ? evCfg.getEnRouteSearchRadius()   : 2_000.0;
        this.dcfcPowerThresholdKw = (evCfg != null) ? evCfg.getDcfcPowerThreshold()    : 50.0;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // ChargingBehaviourScoringEventHandler — delegates to SocProblemCollector
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Forwards scoring events to {@link SocProblemCollector} so it can record SoC
     * problems during the mobsim.  This module is registered as an event handler in
     * {@link InsertEnRouteCharging#get()} following the same pattern as
     * {@link ChangeChargingBehaviour}.
     */
    @Override
    public void handleEvent(ChargingBehaviourScoringEvent event) {
        SocProblemCollector.getInstance().handleEvent(event);
    }

    @Override
    public void reset(int iteration) {
        // SocProblemCollector reset is driven by the IterationStartsListener in GotEVMain.
    }

    // ─────────────────────────────────────────────────────────────────────────
    // PlanStrategyModule interface
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public void prepareReplanning(ReplanningContext replanningContext) {}

    @Override
    public void finishReplanning() {}

    @Override
    public void handlePlan(Plan plan) {
        Id<Person> personId = plan.getPerson().getId();
        SocProblemCollector collector = SocProblemCollector.getInstance();

        // ── Step 1: skip agents with no SoC problems last iteration ──────────
        if (!collector.hadProblems(personId)) return;

        List<SocProblemCollector.SocProblemRecord> problems = collector.getProblemsForPerson(personId);
        if (problems.isEmpty()) return;

        // ── Step 2: resolve risk attitude ────────────────────────────────────
        String riskAttitude = resolveRiskAttitude(plan.getPerson());

        // ── Steps 3–6: attempt one insertion per call ────────────────────────
        for (SocProblemCollector.SocProblemRecord problem : problems) {

            // Step 3: find the car leg in this plan that led to the SoC problem
            int legIdx = findLegIndexForProblem(plan, problem);
            if (legIdx < 0) continue;

            List<PlanElement> elements = plan.getPlanElements();
            Leg targetLeg = (Leg) elements.get(legIdx);

            // Require a NetworkRoute (car leg that has been routed)
            if (!(targetLeg.getRoute() instanceof NetworkRoute)) continue;
            NetworkRoute route = (NetworkRoute) targetLeg.getRoute();
            List<Id<Link>> linkIds = route.getLinkIds();
            if (linkIds.size() < MIN_ROUTE_LINKS) continue;

            // Step 4: enumerate charger candidates along the route
            List<ChargerCandidate> candidates = findCandidatesAlongRoute(linkIds, plan);
            if (candidates.isEmpty()) {
                log.warn(String.format(
                        "InsertEnRoute: no charger within %.0fm of leg route for person %s — skipping",
                        enRouteSearchRadius, personId));
                continue;
            }

            // Step 5: select charger according to risk attitude
            ChargerCandidate selected = selectCandidate(candidates, riskAttitude);

            // Step 6: split the leg and insert the charging stop
            insertChargingStop(plan, legIdx, targetLeg, selected);

            log.info(String.format(
                    "InsertEnRoute: inserted '%s charging' for person %s at charger %s "
                    + "(riskAttitude=%s, power=%.1f kW, candidates=%d)",
                    selected.charger.getChargerType(), personId, selected.charger.getId(),
                    riskAttitude, selected.charger.getPlugPower() / 1000.0, candidates.size()));

            return; // one insertion per handlePlan() call
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Step 2 helper — risk attitude
    // ─────────────────────────────────────────────────────────────────────────

    private String resolveRiskAttitude(Person person) {
        Object attr = person.getAttributes().getAttribute("riskAttitude");
        if (attr != null) {
            String val = attr.toString().toLowerCase(Locale.ROOT).trim();
            if (val.equals("averse") || val.equals("seeking")) return val;
        }
        return "moderate";
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Step 3 — find the car leg in the plan corresponding to the SoC problem
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Returns the index of the car Leg in {@code plan.getPlanElements()} whose end
     * (arrival at the following Activity) best matches {@code problem}.
     *
     * <p>Strategy:
     * <ol>
     *   <li>Find all car legs immediately preceding an Activity whose type is
     *       compatible with {@code problem.activityType}.</li>
     *   <li>Among those, prefer the leg whose departure time is closest to
     *       {@code problem.time} from below; if no departure times are set, take
     *       the first compatible leg.</li>
     * </ol>
     *
     * @return element index of the matching Leg, or -1 if none found
     */
    private int findLegIndexForProblem(Plan plan, SocProblemCollector.SocProblemRecord problem) {
        List<PlanElement> elements = plan.getPlanElements();
        int bestIdx = -1;
        double bestTimeDiff = Double.MAX_VALUE;

        for (int i = 0; i < elements.size() - 1; i++) {
            PlanElement pe = elements.get(i);
            if (!(pe instanceof Leg)) continue;

            Leg leg = (Leg) pe;
            if (!"car".equals(leg.getMode())) continue;
            if (!(leg.getRoute() instanceof NetworkRoute)) continue;

            // The next plan element must be the destination Activity
            PlanElement next = elements.get(i + 1);
            if (!(next instanceof Activity)) continue;
            Activity destAct = (Activity) next;

            // Check type compatibility: e.g. problem "work" matches plan "work charging"
            if (!activityTypeCompatible(destAct.getType(), problem.activityType)) continue;

            // Score by departure time proximity to problem time
            if (leg.getDepartureTime().isDefined()) {
                double dep = leg.getDepartureTime().seconds();
                if (dep <= problem.time) {
                    double diff = problem.time - dep;
                    if (diff < bestTimeDiff) {
                        bestTimeDiff = diff;
                        bestIdx = i;
                    }
                }
            } else if (bestIdx < 0) {
                // No departure time available — take the first compatible leg
                bestIdx = i;
            }
        }
        return bestIdx;
    }

    /**
     * Returns true if {@code planActType} is compatible with {@code problemActType}.
     *
     * <p>Examples:
     * <ul>
     *   <li>{@code "work"} is compatible with {@code "work"}</li>
     *   <li>{@code "work charging"} is compatible with {@code "work"} (plan has charging suffix)</li>
     *   <li>{@code "other"} is compatible with {@code "other charging"} (problem recorded at
     *       a charging activity)</li>
     * </ul>
     */
    private boolean activityTypeCompatible(String planActType, String problemActType) {
        if (planActType == null || problemActType == null) return false;
        // Normalise: strip " charging" / " charging failed" suffixes for comparison
        String normalPlan    = planActType.replace(" charging failed", "").replace(CHARGING_IDENTIFIER, "").trim();
        String normalProblem = problemActType.replace(" charging failed", "").replace(CHARGING_IDENTIFIER, "").trim();
        return normalPlan.equalsIgnoreCase(normalProblem);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Step 4 — enumerate charger candidates along the route
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Returns a list of {@link ChargerCandidate}s sorted by their position index
     * along the route (earliest first).
     *
     * <p>Only links at indices 0 … {@code linkIds.size()-2} (i.e. NOT the last link
     * before the destination) are considered, to avoid inserting a stop immediately
     * at the destination.  Every {@value #LINK_STRIDE}th link is sampled to keep
     * the search tractable on long routes.
     *
     * <p>A candidate is suppressed if the plan already contains a {@code " charging"}
     * activity within {@value #DEDUP_RADIUS_M} m of the charger's coordinate.
     */
    private List<ChargerCandidate> findCandidatesAlongRoute(
            List<Id<Link>> linkIds, Plan plan) {

        // Pre-collect existing charging activity coords for dedup
        List<Coord> existingChargingCoords = collectExistingChargingCoords(plan);

        List<ChargerCandidate> candidates = new ArrayList<>();

        // Search only the first ~90% of the route to leave travel buffer
        int searchLimit = Math.max(MIN_ROUTE_LINKS, (int) (linkIds.size() * 0.90));

        for (int li = 0; li < searchLimit; li += LINK_STRIDE) {
            Link link = network.getLinks().get(linkIds.get(li));
            if (link == null) continue;
            Coord linkCoord = link.getCoord();

            for (ChargerSpecification charger : chargingInfrastructure.getChargerSpecifications().values()) {
                // Private (allowed-vehicles) chargers are excluded from en-route insertion
                if (!charger.getAllowedVehicles().isEmpty()) continue;

                double dist = DistanceUtils.calculateDistance(linkCoord, charger.getCoord());
                if (dist > enRouteSearchRadius) continue;

                // Dedup: skip if existing charging stop is already near this charger
                if (tooCloseToExistingStop(charger.getCoord(), existingChargingCoords)) continue;

                candidates.add(new ChargerCandidate(charger, li, linkCoord));
            }
        }

        // Sort by route position (ascending) to enable risk-attitude slicing
        candidates.sort(Comparator.comparingInt(c -> c.routeLinkIdx));
        return candidates;
    }

    private List<Coord> collectExistingChargingCoords(Plan plan) {
        List<Coord> coords = new ArrayList<>();
        for (PlanElement pe : plan.getPlanElements()) {
            if (pe instanceof Activity) {
                Activity act = (Activity) pe;
                if (act.getType() != null && act.getType().endsWith(CHARGING_IDENTIFIER)) {
                    Coord c = act.getCoord();
                    if (c != null) coords.add(c);
                }
            }
        }
        return coords;
    }

    private boolean tooCloseToExistingStop(Coord chargerCoord, List<Coord> existing) {
        for (Coord ec : existing) {
            if (DistanceUtils.calculateDistance(chargerCoord, ec) < DEDUP_RADIUS_M) return true;
        }
        return false;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Step 5 — select candidate based on risk attitude
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Selects a {@link ChargerCandidate} from the sorted list according to the
     * agent's risk attitude:
     *
     * <ul>
     *   <li><b>averse</b>  – picks from the earliest 25 % of candidates (charge early,
     *       maximise safety buffer).</li>
     *   <li><b>seeking</b> – picks from the latest 25 % of candidates (defer charging,
     *       accept higher risk).</li>
     *   <li><b>moderate</b> – picks uniformly from the middle 50 %.</li>
     * </ul>
     *
     * The list is assumed to be sorted by {@code routeLinkIdx} ascending.
     */
    private ChargerCandidate selectCandidate(List<ChargerCandidate> candidates,
                                             String riskAttitude) {
        int n = candidates.size();
        int selectedIdx;

        switch (riskAttitude) {
            case "averse":
                // First quarter — earliest along the route
                selectedIdx = random.nextInt(Math.max(1, n / 4));
                break;
            case "seeking":
                // Last quarter — latest along the route
                selectedIdx = (n - 1) - random.nextInt(Math.max(1, n / 4));
                break;
            default: // "moderate"
                // Middle half
                int start = n / 4;
                int range = Math.max(1, n / 2);
                selectedIdx = start + random.nextInt(range);
                break;
        }

        // Clamp to valid range (edge case when n is very small)
        selectedIdx = Math.max(0, Math.min(selectedIdx, n - 1));
        return candidates.get(selectedIdx);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Step 6 — split the leg and insert the charging activity
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Replaces the single car leg at {@code legIdx} with:
     * <pre>
     *   [Leg car, no route] → [Activity "other charging", maxDuration] → [Leg car, no route]
     * </pre>
     *
     * Both new legs have their routes cleared so MATSim's router will re-route them
     * during the next QSim run.  The departure time of the first new leg is copied
     * from the original leg (if set).
     */
    private void insertChargingStop(Plan plan, int legIdx, Leg originalLeg,
                                    ChargerCandidate selected) {
        List<PlanElement> elements = plan.getPlanElements();

        // Determine stop duration based on charger tier
        double stopDurationSec = isDcfc(selected.charger)
                ? DCFC_STOP_DURATION_SEC
                : L2_STOP_DURATION_SEC;

        // Build the new charging activity at the charger's coordinate
        Activity chargingAct = popFactory.createActivityFromCoord(
                "other" + CHARGING_IDENTIFIER, selected.charger.getCoord());
        chargingAct.setMaximumDuration(stopDurationSec);

        // Build two new car legs without routes — router fills them in next iteration
        Leg legToCharger   = popFactory.createLeg("car");
        Leg legFromCharger = popFactory.createLeg("car");

        // Preserve departure time on the first leg so timing is consistent
        if (originalLeg.getDepartureTime().isDefined()) {
            legToCharger.setDepartureTime(originalLeg.getDepartureTime().seconds());
        }

        // Splice: remove old leg, insert three elements in its place
        elements.remove(legIdx);
        elements.add(legIdx,     legToCharger);
        elements.add(legIdx + 1, chargingAct);
        elements.add(legIdx + 2, legFromCharger);
    }

    /** Returns true if the charger qualifies as DCFC based on its plug power. */
    private boolean isDcfc(ChargerSpecification charger) {
        return (charger.getPlugPower() / 1000.0) > dcfcPowerThresholdKw;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Inner types
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * A charger found within {@code enRouteSearchRadius} of a route link, together
     * with positional metadata used for risk-attitude selection.
     */
    private static final class ChargerCandidate {
        /** The charger specification. */
        final ChargerSpecification charger;
        /** Index into the route's link-ID list where this charger was found. */
        final int routeLinkIdx;
        /** Coordinate of the link at {@code routeLinkIdx} (used for logging). */
        @SuppressWarnings("unused")
        final Coord nearLinkCoord;

        ChargerCandidate(ChargerSpecification charger, int routeLinkIdx, Coord nearLinkCoord) {
            this.charger       = charger;
            this.routeLinkIdx  = routeLinkIdx;
            this.nearLinkCoord = nearLinkCoord;
        }
    }
}
