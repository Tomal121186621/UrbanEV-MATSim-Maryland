package se.urbanEV.scoring;

import se.urbanEV.config.UrbanEVConfigGroup;
import org.matsim.api.core.v01.Scenario;
import org.matsim.core.api.internal.MatsimParameters;

public class ChargingBehaviourScoringParameters implements MatsimParameters {

    public final double marginalUtilityOfRangeAnxiety_soc;
    public final double utilityOfEmptyBattery;
    public final double marginalUtilityOfWalking_m;
    public final double utilityOfHomeCharging;
    public final double marginalUtilityOfSocDifference;
    public final double defaultRangeAnxietyThreshold;

    // Cost and ToU-related parameters — OmkarP.(2025)
    public final double betaMoney;
    public final double homeChargingCost;
    public final double workChargingCost;
    public final double alphaScaleCost;          // cost scaling
    public final double defaultHomeChargerPower; // kW

    // Power-tier public charging costs ($/kWh) — added for power-tier pricing support
    public final double publicL1Cost;    // L1 chargers  (<  l2PowerThreshold kW)
    public final double publicL2Cost;   // L2 chargers  (l2PowerThreshold – dcfcPowerThreshold kW)
    public final double publicDCFCCost; // DCFC chargers (> dcfcPowerThreshold kW)

    // Power thresholds separating L1/L2/DCFC tiers (kW)
    public final double l2PowerThreshold;   // default 3 kW
    public final double dcfcPowerThreshold; // default 50 kW

    // Value-of-Time (VoT) parameters for waiting and detour disutility
    public final double baseValueOfTimeFactor;    // multiplier on marginalUtilityOfTraveling
    public final double queueAnnoyanceFactor;     // extra multiplier applied when queuing
    public final double detourDisutilityPerHour;  // utility/hour for detour to charger (≤ 0)

    // Person-level parameter override flag
    public final boolean usePersonLevelParams;    // if true, read betaMoney from person attributes

    private ChargingBehaviourScoringParameters(
            final double marginalUtilityOfRangeAnxiety_soc,
            final double utilityOfEmptyBattery,
            final double marginalUtilityOfWalking_m,
            final double utilityOfHomeCharging,
            final double marginalUtilityOfSocDifference,
            final double defaultRangeAnxietyThreshold,
            final double betaMoney,
            final double alphaScaleCost,
            final double defaultHomeChargerPower,
            final double homeChargingCost,
            final double workChargingCost,
            final double publicL1Cost,
            final double publicL2Cost,
            final double publicDCFCCost,
            final double l2PowerThreshold,
            final double dcfcPowerThreshold,
            final double baseValueOfTimeFactor,
            final double queueAnnoyanceFactor,
            final double detourDisutilityPerHour,
            final boolean usePersonLevelParams) {
        this.marginalUtilityOfRangeAnxiety_soc = marginalUtilityOfRangeAnxiety_soc;
        this.utilityOfEmptyBattery = utilityOfEmptyBattery;
        this.marginalUtilityOfWalking_m = marginalUtilityOfWalking_m;
        this.utilityOfHomeCharging = utilityOfHomeCharging;
        this.marginalUtilityOfSocDifference = marginalUtilityOfSocDifference;
        this.defaultRangeAnxietyThreshold = defaultRangeAnxietyThreshold;
        this.betaMoney = betaMoney;
        this.alphaScaleCost = alphaScaleCost;
        this.defaultHomeChargerPower = defaultHomeChargerPower;
        this.homeChargingCost = homeChargingCost;
        this.workChargingCost = workChargingCost;
        this.publicL1Cost = publicL1Cost;
        this.publicL2Cost = publicL2Cost;
        this.publicDCFCCost = publicDCFCCost;
        this.l2PowerThreshold = l2PowerThreshold;
        this.dcfcPowerThreshold = dcfcPowerThreshold;
        this.baseValueOfTimeFactor = baseValueOfTimeFactor;
        this.queueAnnoyanceFactor = queueAnnoyanceFactor;
        this.detourDisutilityPerHour = detourDisutilityPerHour;
        this.usePersonLevelParams = usePersonLevelParams;
    }

    /**
     * Returns the public charging cost per kWh for a charger with the given power output.
     * Tier boundaries are defined by l2PowerThreshold and dcfcPowerThreshold.
     */
    public double getPublicChargingCostForPower(double chargerPowerKw) {
        if (chargerPowerKw >= dcfcPowerThreshold) return publicDCFCCost;
        if (chargerPowerKw >= l2PowerThreshold)   return publicL2Cost;
        return publicL1Cost;
    }

    public static final class Builder {
        private double marginalUtilityOfRangeAnxiety_soc;
        private double utilityOfEmptyBattery;
        private double marginalUtilityOfWalking_m;
        private double utilityOfHomeCharging;
        private double marginalUtilityOfSocDifference;
        private double defaultRangeAnxietyThreshold;
        private double betaMoney;
        private double alphaScaleCost;
        private double defaultHomeChargerPower;
        private double homeChargingCost;
        private double workChargingCost;
        private double publicL1Cost;
        private double publicL2Cost;
        private double publicDCFCCost;
        private double l2PowerThreshold;
        private double dcfcPowerThreshold;
        private double baseValueOfTimeFactor;
        private double queueAnnoyanceFactor;
        private double detourDisutilityPerHour;
        private boolean usePersonLevelParams;

        public Builder(final Scenario scenario) {
            this((UrbanEVConfigGroup) scenario.getConfig().getModules().get(UrbanEVConfigGroup.GROUP_NAME));
        }

        public Builder(final UrbanEVConfigGroup configGroup) {
            marginalUtilityOfRangeAnxiety_soc = configGroup.getRangeAnxietyUtility();
            utilityOfEmptyBattery = configGroup.getEmptyBatteryUtility();
            marginalUtilityOfWalking_m = configGroup.getWalkingUtility();
            utilityOfHomeCharging = configGroup.getHomeChargingUtility();
            marginalUtilityOfSocDifference = configGroup.getSocDifferenceUtility();
            defaultRangeAnxietyThreshold = configGroup.getDefaultRangeAnxietyThreshold();

            // Cost and ToU-related parameters — OmkarP.(2025)
            betaMoney = configGroup.getBetaMoney();
            alphaScaleCost = configGroup.getAlphaScaleCost();
            homeChargingCost = configGroup.getHomeChargingCost();
            workChargingCost = configGroup.getWorkChargingCost();
            defaultHomeChargerPower = configGroup.getDefaultHomeChargerPower();

            // Power-tier public charging costs
            publicL1Cost = configGroup.getPublicL1Cost();
            publicL2Cost = configGroup.getPublicL2Cost();
            publicDCFCCost = configGroup.getPublicDCFCCost();
            l2PowerThreshold = configGroup.getL2PowerThreshold();
            dcfcPowerThreshold = configGroup.getDcfcPowerThreshold();

            // VoT parameters
            baseValueOfTimeFactor = configGroup.getBaseValueOfTimeFactor();
            queueAnnoyanceFactor = configGroup.getQueueAnnoyanceFactor();
            detourDisutilityPerHour = configGroup.getDetourDisutilityPerHour();

            // Person-level override
            usePersonLevelParams = configGroup.isUsePersonLevelParams();

            if (!Double.isFinite(alphaScaleCost) || alphaScaleCost < 0.0) {
                alphaScaleCost = 0.0;
            }
            if (!Double.isFinite(defaultRangeAnxietyThreshold) || defaultRangeAnxietyThreshold <= 0.0) {
                defaultRangeAnxietyThreshold = 0.2;
            }
        }

        public ChargingBehaviourScoringParameters build() {
            return new ChargingBehaviourScoringParameters(
                    marginalUtilityOfRangeAnxiety_soc,
                    utilityOfEmptyBattery,
                    marginalUtilityOfWalking_m,
                    utilityOfHomeCharging,
                    marginalUtilityOfSocDifference,
                    defaultRangeAnxietyThreshold,
                    betaMoney,
                    alphaScaleCost,
                    defaultHomeChargerPower,
                    homeChargingCost,
                    workChargingCost,
                    publicL1Cost,
                    publicL2Cost,
                    publicDCFCCost,
                    l2PowerThreshold,
                    dcfcPowerThreshold,
                    baseValueOfTimeFactor,
                    queueAnnoyanceFactor,
                    detourDisutilityPerHour,
                    usePersonLevelParams
            );
        }
    }
}
