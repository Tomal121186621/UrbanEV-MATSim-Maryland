package se.urbanEV.scoring;

import com.google.inject.Inject;
import se.urbanEV.stats.ChargingBehaviorScoresCollector;
import org.matsim.api.core.v01.events.Event;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.scoring.SumScoringFunction;
import se.urbanEV.charging.ChargingCostUtils;

public class ChargingBehaviourScoring implements SumScoringFunction.ArbitraryEventScoring {

    public enum ScoreComponents {
        RANGE_ANXIETY,
        EMPTY_BATTERY,
        WALKING_DISTANCE,
        HOME_CHARGING,
        ENERGY_BALANCE,
        CHARGING_COST,   // OmkarP.(2025): monetary cost of energy
        DETOUR_TIME,     // disutility of extra travel to reach an en-route charger
        QUEUE_WAIT       // disutility of waiting for a free plug
    }

    /** Fallback value-of-time when no person attribute is set (USD/hr for median MD worker). */
    private static final double DEFAULT_VALUE_OF_TIME_USD_PER_HR = 15.0;

    private double score;
    private static final String CHARGING_IDENTIFIER = " charging";
    private static final String LAST_ACT_IDENTIFIER = " end";
    private static final double TOU_STEP_SEC = 15.0 * 60.0;

    private final ChargingBehaviorScoresCollector collector =
            ChargingBehaviorScoresCollector.getInstance();

    final ChargingBehaviourScoringParameters params;
    Person person;

    @Inject
    public ChargingBehaviourScoring(final ChargingBehaviourScoringParameters params, Person person) {
        this.params = params;
        this.person = person;
    }

    // -------------------------------------------------------------------------
    // Person-level parameter helpers
    // -------------------------------------------------------------------------

    /** Returns betaMoney: person-attribute if usePersonLevelParams, else config default. */
    private double resolvedBetaMoney() {
        double beta = params.betaMoney;
        if (params.usePersonLevelParams) {
            Object attr = person.getAttributes().getAttribute("betaMoney");
            if (attr != null) {
                try { beta = Double.parseDouble(attr.toString()); }
                catch (NumberFormatException ignored) { }
            }
        }
        return beta;
    }

    /**
     * Returns the rangeAnxietyThreshold for this person.
     * Person attribute takes priority (already written by MobsimScopeEventHandling at startup);
     * falls back to config default.
     */
    private double resolvedRangeAnxietyThreshold() {
        Object attr = person.getAttributes().getAttribute("rangeAnxietyThreshold");
        if (attr != null) {
            try { return Double.parseDouble(attr.toString()); }
            catch (NumberFormatException ignored) { }
        }
        return params.defaultRangeAnxietyThreshold;
    }

    /**
     * Returns value-of-time in USD/hr.
     * If usePersonLevelParams=true and the person has a "valueOfTime" attribute, use it;
     * otherwise fall back to DEFAULT_VALUE_OF_TIME_USD_PER_HR.
     */
    private double resolvedValueOfTime() {
        if (params.usePersonLevelParams) {
            Object attr = person.getAttributes().getAttribute("valueOfTime");
            if (attr != null) {
                try { return Double.parseDouble(attr.toString()); }
                catch (NumberFormatException ignored) { }
            }
        }
        return DEFAULT_VALUE_OF_TIME_USD_PER_HR;
    }

    // -------------------------------------------------------------------------
    // Event handler
    // -------------------------------------------------------------------------

    @Override
    public void handleEvent(Event event) {
        if (!event.getEventType().equals("scoring")) return;

        ChargingBehaviourScoringEvent ev = (ChargingBehaviourScoringEvent) event;

        boolean costOnly    = ev.isCostOnly();
        double  soc         = ev.getSoc();
        String  activityType = ev.getActivityType();

        // Resolve person-level parameters once per event — shared by cost components below.
        double resolvedBeta     = resolvedBetaMoney();
        double effectiveBeta    = resolvedBeta * params.alphaScaleCost;
        double valueOfTime      = resolvedValueOfTime();

        // ── Non-monetary components (skipped for cost-only events) ────────────

        if (!costOnly) {

            // 1. RANGE_ANXIETY: penalty when SoC is below threshold
            double threshold = resolvedRangeAnxietyThreshold();
            if (soc > 0 && soc < threshold) {
                double delta = params.marginalUtilityOfRangeAnxiety_soc
                             * (threshold - soc) / threshold;
                collector.addScoringComponentValue(ScoreComponents.RANGE_ANXIETY, delta);
                collector.addScoringPerson(ScoreComponents.RANGE_ANXIETY, person.getId());
                score += delta;
            }

            // 2. EMPTY_BATTERY: severe penalty when SoC reaches zero
            if (soc == 0) {
                double delta = params.utilityOfEmptyBattery;
                collector.addScoringComponentValue(ScoreComponents.EMPTY_BATTERY, delta);
                collector.addScoringPerson(ScoreComponents.EMPTY_BATTERY, person.getId());
                score += delta;
            }

            // 3. WALKING_DISTANCE: exponential penalty for walking to charger
            double walkingDistance = ev.getWalkingDistance();
            if (activityType != null && activityType.contains(CHARGING_IDENTIFIER)) {
                double beta = 0.005; // Geurs & van Wee (2004) Eq. 1
                double delta = params.marginalUtilityOfWalking_m
                             * (1.0 - Math.exp(-beta * walkingDistance));
                collector.addScoringComponentValue(ScoreComponents.WALKING_DISTANCE, delta);
                collector.addScoringPerson(ScoreComponents.WALKING_DISTANCE, person.getId());
                score += delta;
            }

            // 4. HOME_CHARGING: reward for charging at home when a home charger exists
            boolean hasHomeCharger =
                    person.getAttributes().getAttribute("homeChargerPower") != null;
            if (hasHomeCharger
                    && activityType != null
                    && activityType.equals("home" + CHARGING_IDENTIFIER)) {
                double delta = params.utilityOfHomeCharging;
                collector.addScoringComponentValue(ScoreComponents.HOME_CHARGING, delta);
                collector.addScoringPerson(ScoreComponents.HOME_CHARGING, person.getId());
                score += delta;
            }

            // 5. ENERGY_BALANCE: penalty when end SoC < start SoC at last activity
            if (activityType != null && activityType.contains(LAST_ACT_IDENTIFIER)) {
                double effectiveSoc = soc;
                if (activityType.contains(CHARGING_IDENTIFIER)) {
                    // Workaround: treat still-charging last activity as fully charged
                    effectiveSoc = 1.0;
                }
                double socDiff = effectiveSoc - ev.getStartSoc();
                if (socDiff <= 0) {
                    double delta = params.marginalUtilityOfSocDifference * Math.abs(socDiff);
                    collector.addScoringComponentValue(ScoreComponents.ENERGY_BALANCE, delta);
                    score += delta;
                } else {
                    collector.addScoringComponentValue(ScoreComponents.ENERGY_BALANCE, 0.0);
                }
                collector.addScoringPerson(ScoreComponents.ENERGY_BALANCE, person.getId());
            }
        }

        // ── Monetary / time-cost components (always evaluated when data is present) ─

        String  chargerType      = ev.getChargerType();
        Double  energyChargedKWh = ev.getEnergyChargedKWh();

        // 6. CHARGING_COST: energy cost with ToU multiplier and power-tier pricing
        if (energyChargedKWh != null && energyChargedKWh > 0.0 && chargerType != null) {

            double unitPrice;
            if ("home".equals(chargerType)) {
                unitPrice = params.homeChargingCost;
            } else if ("work".equals(chargerType)) {
                unitPrice = params.workChargingCost;
            } else {
                // Public: determine tier from charger plug power
                Double plugKw = ev.getChargerPowerKw();
                if (plugKw != null && plugKw > params.dcfcPowerThreshold) {
                    unitPrice = params.publicDCFCCost;
                } else if (plugKw != null && plugKw > params.l2PowerThreshold) {
                    unitPrice = params.publicL2Cost;
                } else {
                    unitPrice = params.publicL1Cost; // default to L1 when power unknown
                }
            }

            if (unitPrice > 0.0 && effectiveBeta != 0.0) {
                double touMultiplier = 1.0;

                // Time-of-use multiplier applies only to home charging
                if ("home".equals(chargerType)) {
                    Double pricingTime = ev.getPricingTime();
                    double tStart = (pricingTime != null) ? pricingTime : event.getTime();

                    double powerKW = params.defaultHomeChargerPower;
                    Object pAttr = person.getAttributes().getAttribute("homeChargerPower");
                    if (pAttr != null) {
                        try { powerKW = Double.parseDouble(pAttr.toString()); }
                        catch (Exception ignored) { }
                    }

                    if (powerKW > 0.0) {
                        double durationSec = (energyChargedKWh / powerKW) * 3600.0;
                        if (durationSec > 1.0) {
                            double tEnd  = tStart + durationSec;
                            double wSum  = 0.0;
                            double dtSum = 0.0;
                            for (double tt = tStart; tt < tEnd - 1e-6; tt += TOU_STEP_SEC) {
                                double dt = Math.min(TOU_STEP_SEC, tEnd - tt);
                                double m  = ChargingCostUtils.getHourlyCostMultiplier(tt);
                                wSum  += m * dt;
                                dtSum += dt;
                            }
                            touMultiplier = (dtSum > 0.0)
                                    ? (wSum / dtSum)
                                    : ChargingCostUtils.getHourlyCostMultiplier(tStart);
                        } else {
                            touMultiplier = ChargingCostUtils.getHourlyCostMultiplier(tStart);
                        }
                    } else {
                        touMultiplier = ChargingCostUtils.getHourlyCostMultiplier(tStart);
                    }
                }

                double chargingCost = energyChargedKWh * unitPrice * touMultiplier;
                double delta = effectiveBeta * chargingCost; // effectiveBeta < 0 → disutility
                collector.addScoringComponentValue(ScoreComponents.CHARGING_COST, delta);
                collector.addScoringPerson(ScoreComponents.CHARGING_COST, person.getId());
                score += delta;
            }
        }

        // 7. DETOUR_TIME: disutility of extra travel to reach an en-route charger
        //    delta = detourDisutilityPerHour * hours + effectiveBeta * VoT * hours
        //    Both terms are negative → net disutility.
        Double detourSec = ev.getDetourSeconds();
        if (detourSec != null && detourSec > 0.0) {
            double detourHours = detourSec / 3600.0;
            double delta = params.detourDisutilityPerHour * detourHours  // direct utility loss
                         + effectiveBeta * valueOfTime * detourHours;    // monetary equivalent
            collector.addScoringComponentValue(ScoreComponents.DETOUR_TIME, delta);
            collector.addScoringPerson(ScoreComponents.DETOUR_TIME, person.getId());
            score += delta;
        }

        // 8. QUEUE_WAIT: disutility of waiting for a free charger plug
        //    delta = effectiveBeta * VoT * queueAnnoyanceFactor * hours
        //    effectiveBeta < 0, VoT > 0, annoyanceFactor > 1 → net disutility, amplified.
        Double queueSec = ev.getQueueWaitSeconds();
        if (queueSec != null && queueSec > 0.0) {
            double queueHours = queueSec / 3600.0;
            double delta = effectiveBeta * valueOfTime * params.queueAnnoyanceFactor * queueHours;
            collector.addScoringComponentValue(ScoreComponents.QUEUE_WAIT, delta);
            collector.addScoringPerson(ScoreComponents.QUEUE_WAIT, person.getId());
            score += delta;
        }
    }

    @Override public void finish() {}

    @Override
    public double getScore() {
        return score;
    }
}
