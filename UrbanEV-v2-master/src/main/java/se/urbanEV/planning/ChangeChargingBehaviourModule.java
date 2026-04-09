package se.urbanEV.planning;

import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.scoring.ChargingBehaviourScoringEvent;
import se.urbanEV.scoring.ChargingBehaviourScoringEventHandler;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.network.Network;
import org.matsim.api.core.v01.population.*;
import org.matsim.api.core.v01.replanning.PlanStrategyModule;
import org.matsim.core.replanning.ReplanningContext;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class ChangeChargingBehaviourModule implements PlanStrategyModule, ChargingBehaviourScoringEventHandler {

    private static final String CHARGING_IDENTIFIER = " charging";
    private static final String CHARGING_FAILED_IDENTIFIER = " charging failed";
    private final Random random = org.matsim.core.gbl.MatsimRandom.getLocalInstance();
    private Scenario scenario;
    private Network network;
    private Population population;
    private UrbanEVConfigGroup evCfg;
    private int maxNumberSimultaneousPlanChanges;
    private Double timeAdjustmentProbability;
    private int maxTimeFlexibility;

    ChangeChargingBehaviourModule(Scenario scenario) {
        this.scenario = scenario;
        this.network = this.scenario.getNetwork();
        this.population = this.scenario.getPopulation();
        this.evCfg = (UrbanEVConfigGroup) scenario.getConfig().getModules().get("urban_ev");
        this.maxNumberSimultaneousPlanChanges = evCfg.getMaxNumberSimultaneousPlanChanges();
        this.timeAdjustmentProbability = evCfg.getTimeAdjustmentProbability();
        this.maxTimeFlexibility = evCfg.getMaxTimeFlexibility();
    }

    @Override
    public void finishReplanning() {
    }

    @Override
    public void handlePlan(Plan plan) {
        int numberOfChanges = 1 + random.nextInt(maxNumberSimultaneousPlanChanges);

        for (int c = 0; c < numberOfChanges; c++ ) {
            List<PlanElement> planElements = plan.getPlanElements();
            int max = planElements.size();

            // get activity ids of activities with and without charging
            ArrayList<Integer> successfulChargingActIds = new ArrayList<>();
            ArrayList<Integer> failedChargingActIds = new ArrayList<>();
            ArrayList<Integer> noChargingActIds = new ArrayList<>();

            // loop starts at 2 because car should never be charging at start of simulation
            for (int i = 2; i < max; i++) {
                PlanElement pe = planElements.get(i);
                if (pe instanceof Activity) {
                    Activity act = (Activity) pe;
                    if (act.getType().endsWith(CHARGING_IDENTIFIER)) {
                        successfulChargingActIds.add(i);
                    } else if (act.getType().endsWith(CHARGING_FAILED_IDENTIFIER)
                               || act.getType().contains(" failed")) {
                        // Strip ALL charging/failed suffixes to prevent accumulation
                        // across iterations (e.g., "other failed charging failed" → "other")
                        failedChargingActIds.add(i);
                        String baseType = act.getType()
                                .replace(CHARGING_FAILED_IDENTIFIER, "")
                                .replace(CHARGING_IDENTIFIER, "")
                                .replace(" failed", "")
                                .trim();
                        act.setType(baseType);
                    } else {
                        noChargingActIds.add(i);
                    }
                }
            }

            // with some probability try changing start time of failed charging activity (end time of previous activity)
            if (failedChargingActIds.size() > 0 && random.nextDouble() < timeAdjustmentProbability) {
                changeChargingActivityTime(planElements, failedChargingActIds);
            } else {
                // number of charging attempts that were successful
                int nSuccessfulCharging = successfulChargingActIds.size();
                // number of failed charging attempts
                int nFailedCharging = failedChargingActIds.size();
                // number of activities without charging attempt
                int nNoCharging = noChargingActIds.size();
                // sum of activities with successful attempts and activities without charging attempts
                int nTotal = nSuccessfulCharging + nNoCharging;

                // assign weights to different strategies based on successful and failed attempts
                double wChangeFailed = (nFailedCharging == 0 || nNoCharging == 0) ? 0 : 2;
                double wChangeSuccessful = (nSuccessfulCharging == 0 || nNoCharging == 0) ? 0 : 1;
                double wAdd = (double) nNoCharging / nTotal;
                double wRemove = (double) nSuccessfulCharging / nTotal;

                // decide which strategy to use: add/remove/change
                // Todo: Beautify and simplify this!
                double sumOfWeights = wAdd + wRemove + wChangeSuccessful + wChangeFailed;
                double w = sumOfWeights * random.nextDouble();
                w -= wChangeFailed;
                if (w <= 0) {
                    changeChargingActivity(planElements, failedChargingActIds, noChargingActIds);
                } else {
                    w -= wChangeSuccessful;
                    if (w <= 0) {
                        changeChargingActivity(planElements, successfulChargingActIds, noChargingActIds);
                    } else {
                        w -= wAdd;
                        if (w <= 0) {
                            addChargingActivity(planElements, noChargingActIds);
                        } else {
                            removeChargingActivity(planElements, successfulChargingActIds);
                        }
                    }
                }
            }
        }
    }

    private void changeChargingActivityTime(List<PlanElement> planElements, ArrayList<Integer> failedChargingActIds) {
        // select random failed charging activity and try changing end time of previous activity
        int n = failedChargingActIds.size();
        if (n > 0) {
            int randInt = random.nextInt(n);
            int actId = failedChargingActIds.get(randInt);
            if (actId >= 2) {
                Activity selectedActivity = (Activity) planElements.get(actId);
                Leg previousLeg = (Leg) planElements.get(actId - 1);
                Activity previousActivity = (Activity) planElements.get(actId - 2);
                double timeDifference = random.nextDouble() * maxTimeFlexibility; // 0 to 10 minutes
                double earliestPossibleTime = 0;
                if (actId >= 4) {
                    Activity earlierAct = (Activity) planElements.get(actId - 4);
                    if (earlierAct.getEndTime().isDefined()) {
                        earliestPossibleTime = earlierAct.getEndTime().seconds();
                    }
                }
                if (previousActivity.getEndTime().isDefined()
                        && previousActivity.getEndTime().seconds() - timeDifference > earliestPossibleTime) {
                    previousActivity.setEndTime(previousActivity.getEndTime().seconds() - timeDifference);
                    if (previousLeg.getDepartureTime().isDefined()) {
                        previousLeg.setDepartureTime(previousLeg.getDepartureTime().seconds() - timeDifference);
                    }
                    selectedActivity.setType(selectedActivity.getType() + CHARGING_IDENTIFIER);
                }
            }
        }
    }

    /**
     * Select an activity to add charging, weighted by estimated charging cost.
     * Cheaper locations (home, work) are preferred over expensive public chargers.
     * Uses softmax-style weighting: weight = exp(-beta * cost_per_kWh).
     *
     * <p>Based on Ge et al. (2023) price-responsive EV charging model and
     * Chakraborty et al. (2020) price elasticity findings.
     *
     * @see UrbanEVConfigGroup#getChargingCostSensitivity()
     */
    private void addChargingActivity(List<PlanElement> planElements, ArrayList<Integer> noChargingActIds) {
        int n = noChargingActIds.size();
        if (n == 0) return;

        double beta = evCfg.getChargingCostSensitivity(); // default 3.0

        // Calculate cost-weighted probabilities for each candidate
        double[] weights = new double[n];
        double totalWeight = 0;

        for (int i = 0; i < n; i++) {
            int actId = noChargingActIds.get(i);
            Activity act = (Activity) planElements.get(actId);
            String actType = act.getType();

            // Estimate per-kWh charging cost at this location type
            double costPerKwh;
            if (actType.startsWith("home")) {
                costPerKwh = evCfg.getHomeChargingCost();       // $0.13
            } else if (actType.startsWith("work")) {
                costPerKwh = evCfg.getWorkChargingCost();       // $0.00
            } else {
                costPerKwh = evCfg.getPublicL2Cost();           // $0.25
            }

            // Softmax: lower cost → higher weight
            weights[i] = Math.exp(-beta * costPerKwh);
            totalWeight += weights[i];
        }

        // Weighted random selection
        double r = random.nextDouble() * totalWeight;
        double cumulative = 0;
        int selectedIdx = 0;
        for (int i = 0; i < n; i++) {
            cumulative += weights[i];
            if (r <= cumulative) {
                selectedIdx = i;
                break;
            }
        }

        int actId = noChargingActIds.get(selectedIdx);
        Activity selectedActivity = (Activity) planElements.get(actId);
        selectedActivity.setType(selectedActivity.getType() + CHARGING_IDENTIFIER);
    }

    private void removeChargingActivity(List<PlanElement> planElements, ArrayList<Integer> successfulChargingActIds) {
        // select random activity with charging and change to activity without charging
        int n = successfulChargingActIds.size();
        if (n > 0) {
            int randInt = random.nextInt(n);
            int actId = successfulChargingActIds.get(randInt);
            Activity selectedActivity = (Activity) planElements.get(actId);
            selectedActivity.setType(selectedActivity.getType().replace(CHARGING_IDENTIFIER, ""));
        }
    }

    private void changeChargingActivity(List<PlanElement> planElements,
                                ArrayList<Integer> chargingActIds,
                                ArrayList<Integer> noChargingActIds) {
        // select random activity with charging and change to activity without charging
        int chargingActId = chargingActIds.get(random.nextInt(chargingActIds.size()));
        Activity selectedActivity = (Activity) planElements.get(chargingActId);
        selectedActivity.setType(selectedActivity.getType().replace(CHARGING_IDENTIFIER, ""));

        // select activity without charging close to original activity using gaussian distribution and change to activity with charging
        double gaussId = 0.0;
        while (gaussId < 1 || gaussId > planElements.size()) {
            gaussId = 5 * random.nextGaussian() + chargingActId;
        }
        double dMin = planElements.size();
        int closestNoChargingActId = 0;
        for (int noChargingActId : noChargingActIds) {
            double d = Math.abs(gaussId - noChargingActId);
            if (d < dMin) {
                dMin = d;
                closestNoChargingActId = noChargingActId;
            }
        }
        Activity closestNoChargingActivity = (Activity) planElements.get(closestNoChargingActId);
        closestNoChargingActivity.setType(closestNoChargingActivity.getType() + CHARGING_IDENTIFIER);
    }

    @Override
    public void prepareReplanning(ReplanningContext replanningContext) {
    }

    @Override
    public void handleEvent(ChargingBehaviourScoringEvent event) {
        // 1) Ignore synthetic "cost-only" events from VehicleChargingHandler
        //    (these are only for monetary scoring and should not drive replanning).
        if (event.isCostOnly()) {
            return;
        }

        // 2) Null guards: if SOC or startSOC is missing, do not touch subpopulation.
        Double socObj = event.getSoc();
        Double startSocObj = event.getStartSoc();
        String actType = event.getActivityType();

        if (socObj == null || startSocObj == null || actType == null) {
            return;
        }

        double soc = socObj;
        double startSoc = startSocObj;
        boolean isLastAct = actType.contains("end");

        // 3) Critical if:
        //    - battery is empty at any scoring event, OR
        //    - at the last activity, SOC dropped far from start SOC in a "bad" way.
        boolean isCritical;

        if (soc <= 0.0) {
            // Empty battery → always critical.
            isCritical = true;
        } else if (isLastAct) {
            double deltaSoc = Math.abs(soc - startSoc);
            // Use a probabilistic threshold as before, but keep it bounded and explicit.
            double threshold = random.nextDouble();
            isCritical = deltaSoc > threshold;
        } else {
            // Intermediate activities are not decisive for (non-)critical classification.
            isCritical = false;
        }

        Person person = population.getPersons().get(event.getPersonId());
        if (person == null) {
            return;
        }

        if (isCritical) {
            // Mark agent as "criticalSOC" → always replanned via strategy settings.
            person.getAttributes().putAttribute("subpopulation", "criticalSOC");
        } else {
            // Reset to default "nonCriticalSOC" for standard replanning probability.
            person.getAttributes().putAttribute("subpopulation", "nonCriticalSOC");
        }
    }

    @Override
    public void reset(int iteration) {
    }
}
