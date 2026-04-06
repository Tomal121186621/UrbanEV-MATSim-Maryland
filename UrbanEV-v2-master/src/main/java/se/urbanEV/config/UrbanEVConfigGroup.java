package se.urbanEV.config;

import org.matsim.core.config.ReflectiveConfigGroup;

import javax.validation.constraints.NotNull;
import javax.validation.constraints.Positive;
import javax.validation.constraints.PositiveOrZero;
import java.util.Map;
import org.apache.log4j.Logger;

public final class UrbanEVConfigGroup extends ReflectiveConfigGroup {
    private static final Logger log = Logger.getLogger(UrbanEVConfigGroup.class);

    public static final String GROUP_NAME = "urban_ev";

    // ── Scoring utility constants ────────────────────────────────────────────

    private static final String RANGE_ANXIETY_UTILITY = "rangeAnxietyUtility";
    static final String RANGE_ANXIETY_UTILITY_EXP = "[utils/percent_points_of_soc_under_threshold] utility for going below battery threshold. negative";

    private static final String EMPTY_BATTERY_UTILITY = "emptyBatteryUtility";
    static final String EMPTY_BATTERY_UTILITY_EXP = "[utils] utility for empty battery. should not happen. very negative";

    private static final String WALKING_UTILITY = "walkingUtility";
    static final String WALKING_UTILITY_EXP = "[utils/m] utility for walking from charger to activity. negative";

    private static final String HOME_CHARGING_UTILITY = "homeChargingUtility";
    static final String HOME_CHARGING_UTILITY_EXP = "[utils] utility for using private home charger. positive";

    private static final String SOC_DIFFERENCE_UTILITY = "socDifferenceUtility";
    static final String SOC_DIFFERENCE_UTILITY_EXP = "[utils] utility for difference between start and end soc";

    public static final String VEHICLE_TYPES_FILE = "vehicleTypesFile";
    static final String VEHICLE_TYPES_FILE_EXP = "Location of the vehicle types file";

    public static final String DEFAULT_RANGE_ANXIETY_THRESHOLD = "defaultRangeAnxietyThreshold";
    static final String DEFAULT_RANGE_ANXIETY_THRESHOLD_EXP = "Default threshold for scoring. Set person attribute to overwrite. [% soc]";

    public static final String PARKING_SEARCH_RADIUS = "parkingSearchRadius";
    static final String PARKING_SEARCH_RADIUS_EXP = "Radius around activity location in which agents looks for available chargers [m]";

    // ── Replanning constants ─────────────────────────────────────────────────

    public static final String MAXNUMBERSIMULTANEOUSPLANCHANGES = "maxNumberSimultaneousPlanChanges";
    static final String MAXNUMBERSIMULTANEOUSPLANCHANGES_EXP = "The maximum number of changes to a persons charging plan that are introduced in one replanning step.";

    public static final String TIMEADJUSTMENTPROBABILITY = "timeAdjustmentProbability";
    static final String TIMEADJUSTMENTPROBABILITY_EXP = "The probability with which a persons decides to adjust their activity end times in order to increase their chances for a free charging spot at their next activity.";

    public static final String MAXTIMEFLEXIBILITY = "maxTimeFlexibility";
    static final String MAXTIMEFLEXIBILITY_EXP = "The maximum time span a person is willing to adjust their activity end times in order to increase their chances for a free charging spot at their next activity [s].";

    // ── Charger generation constants ─────────────────────────────────────────

    public static final String GENERATE_HOME_CHARGERS_BY_PERCENTAGE = "generateHomeChargersByPercentage";
    static final String GENERATE_HOME_CHARGERS_BY_PERCENTAGE_EXP = "If set to true, home charger information from the population file will be ignored. Instead home chargers will be generated randomly given the homeChargerPercentage share. [true/false]";

    public static final String GENERATE_WORK_CHARGERS_BY_PERCENTAGE = "generateWorkChargersByPercentage";
    static final String GENERATE_WORK_CHARGERS_BY_PERCENTAGE_EXP = "If set to true, work charger information from the population file will be ignored. Instead work chargers will be generated randomly given the workChargerPercentage share. [true/false]";

    public static final String HOME_CHARGER_PERCENTAGE = "homeChargerPercentage";
    static final String HOME_CHARGER_PERCENTAGE_EXP = "Share of the population that will be equipped with a home charger if generateHomeChargersByPercentage is set to true. [%]";

    public static final String WORK_CHARGER_PERCENTAGE = "workChargerPercentage";
    static final String WORK_CHARGER_PERCENTAGE_EXP = "Share of the population that will be equipped with a work charger if generateWorkChargersByPercentage is set to true. [%]";

    public static final String DEFAULT_HOME_CHARGER_POWER = "defaultHomeChargerPower";
    static final String DEFAULT_HOME_CHARGER_POWER_EXP = "The power of home chargers if generateHomeChargersByPercentage is set to true [kW].";

    public static final String DEFAULT_WORK_CHARGER_POWER = "defaultWorkChargerPower";
    static final String DEFAULT_WORK_CHARGER_POWER_EXP = "The power of work chargers if generateWorkChargersByPercentage is set to true [kW].";

    // ── Charging cost constants ──────────────────────────────────────────────

    private static final String HOME_CHARGING_COST = "homeChargingCost";
    static final String HOME_CHARGING_COST_EXP = "[currency/kWh] unit energy cost at home chargers. 0.0 disables monetary charging at home.";

    private static final String WORK_CHARGING_COST = "workChargingCost";
    static final String WORK_CHARGING_COST_EXP = "[currency/kWh] unit energy cost at work chargers. 0.0 disables monetary charging at work.";

    private static final String PUBLIC_L1_COST = "publicL1Cost";
    static final String PUBLIC_L1_COST_EXP = "[currency/kWh] unit energy cost at public Level 1 chargers (below l2PowerThreshold kW).";

    private static final String PUBLIC_L2_COST = "publicL2Cost";
    static final String PUBLIC_L2_COST_EXP = "[currency/kWh] unit energy cost at public Level 2 chargers (l2PowerThreshold to dcfcPowerThreshold kW).";

    private static final String PUBLIC_DCFC_COST = "publicDCFCCost";
    static final String PUBLIC_DCFC_COST_EXP = "[currency/kWh] unit energy cost at public DC fast chargers (above dcfcPowerThreshold kW).";

    private static final String L2_POWER_THRESHOLD = "l2PowerThreshold";
    static final String L2_POWER_THRESHOLD_EXP = "[kW] power cutoff between L1 and L2 pricing tiers. Chargers below this use publicL1Cost; at or above use publicL2Cost.";

    private static final String DCFC_POWER_THRESHOLD = "dcfcPowerThreshold";
    static final String DCFC_POWER_THRESHOLD_EXP = "[kW] power cutoff between L2 and DCFC pricing tiers. Chargers at or above this use publicDCFCCost.";

    private static final String BETA_MONEY = "betaMoney";
    static final String BETA_MONEY_EXP = "[utils/currency] marginal utility of money for EV charging costs. Typically negative; 0.0 disables charging cost in scoring.";

    private static final String ALPHA_SCALE_COST = "alphaScaleCost";
    static final String ALPHA_SCALE_COST_EXP = "[dimensionless] technical scaling factor applied to betaMoney in EV scoring. 1.0 = no scaling; values << 1.0 dampen the money term.";

    // ── VoT constants ────────────────────────────────────────────────────────

    private static final String BASE_VALUE_OF_TIME_FACTOR = "baseValueOfTimeFactor";
    static final String BASE_VALUE_OF_TIME_FACTOR_EXP = "[dimensionless] fraction of hourly wage used as value-of-time for charging waiting. E.g. 0.4 = 40% of wage.";

    private static final String QUEUE_ANNOYANCE_FACTOR = "queueAnnoyanceFactor";
    static final String QUEUE_ANNOYANCE_FACTOR_EXP = "[dimensionless] multiplier on VoT when waiting in a charger queue (>1 means queue time feels worse than regular waiting).";

    private static final String DETOUR_DISUTILITY_PER_HOUR = "detourDisutilityPerHour";
    static final String DETOUR_DISUTILITY_PER_HOUR_EXP = "[utils/hr] disutility per hour of detour travel to reach a charger. Typically negative.";

    // ── En-route charging constants ──────────────────────────────────────────

    private static final String ENABLE_EN_ROUTE_CHARGING = "enableEnRouteCharging";
    static final String ENABLE_EN_ROUTE_CHARGING_EXP = "Enable the InsertEnRouteCharging replanning strategy. [true/false]";

    private static final String EN_ROUTE_SEARCH_RADIUS = "enRouteSearchRadius";
    static final String EN_ROUTE_SEARCH_RADIUS_EXP = "[m] search radius from route to find chargers for en-route charging insertion.";

    private static final String EN_ROUTE_SAFETY_BUFFER = "enRouteSafetyBuffer";
    static final String EN_ROUTE_SAFETY_BUFFER_EXP = "[fraction of capacity, 0-1] extra SoC buffer added when deciding whether en-route charging is needed. Higher = more conservative.";

    private static final String SOC_PROBLEM_THRESHOLD = "socProblemThreshold";
    static final String SOC_PROBLEM_THRESHOLD_EXP = "[fraction of capacity, 0-1] SoC below which an agent is flagged as having a charging problem and aggressively replans.";

    // ── Heterogeneity constants ──────────────────────────────────────────────

    private static final String USE_PERSON_LEVEL_PARAMS = "usePersonLevelParams";
    static final String USE_PERSON_LEVEL_PARAMS_EXP = "When true, read betaMoney and rangeAnxietyThreshold from person attributes instead of global config values. Enables agent-level heterogeneity.";

    // ── Smart charging constants ─────────────────────────────────────────────

    private static final String ENABLE_SMART_CHARGING = "enableSmartCharging";
    private static final String ALPHA_SCALE_TEMPORAL = "alphaScaleTemporal";
    private static final String AWARENESS_FACTOR = "awarenessFactor";
    private static final String COINCIDENCE_FACTOR = "coincidenceFactor";


    // ═════════════════════════════════════════════════════════════════════════
    //  Field declarations
    // ═════════════════════════════════════════════════════════════════════════

    // ── Charger generation fields ────────────────────────────────────────────

    private boolean generateHomeChargersByPercentage = false;
    private boolean generateWorkChargersByPercentage = false;

    @PositiveOrZero
    private double homeChargerPercentage = 0.0;

    @PositiveOrZero
    private double workChargerPercentage = 0.0;

    @PositiveOrZero
    private double defaultHomeChargerPower = 11.0;

    @PositiveOrZero
    private double defaultWorkChargerPower = 11.0;

    // ── Scoring fields ───────────────────────────────────────────────────────

    @NotNull
    private double rangeAnxietyUtility = -5;

    @NotNull
    private double emptyBatteryUtility = -10;

    @NotNull
    private double walkingUtility = -1;

    @NotNull
    private double homeChargingUtility = +1;

    @NotNull
    private double socDifferenceUtility = -10;

    @Positive
    private double defaultRangeAnxietyThreshold = 0.2;

    @NotNull
    private String vehicleTypesFile = null;

    // ── Charging search fields ───────────────────────────────────────────────

    @Positive
    private int parkingSearchRadius = 500;

    // ── Replanning fields ────────────────────────────────────────────────────

    @Positive
    private int maxNumberSimultaneousPlanChanges = 2;

    @PositiveOrZero
    private Double timeAdjustmentProbability = 0.1;

    @PositiveOrZero
    private int maxTimeFlexibility = 600;

    // ── Charging cost fields ─────────────────────────────────────────────────

    @NotNull
    private double betaMoney = 0.00;

    @PositiveOrZero
    private double homeChargingCost = 0.13;

    @PositiveOrZero
    private double workChargingCost = 0.0;

    @PositiveOrZero
    private double publicL1Cost = 0.18;

    @PositiveOrZero
    private double publicL2Cost = 0.25;

    @PositiveOrZero
    private double publicDCFCCost = 0.48;

    @PositiveOrZero
    private double alphaScaleCost = 1.0;

    // ── Power tier thresholds ────────────────────────────────────────────────

    @Positive
    private double l2PowerThreshold = 3.0;

    @Positive
    private double dcfcPowerThreshold = 50.0;

    // ── VoT fields ───────────────────────────────────────────────────────────

    @PositiveOrZero
    private double baseValueOfTimeFactor = 0.4;

    @PositiveOrZero
    private double queueAnnoyanceFactor = 2.0;

    @NotNull
    private double detourDisutilityPerHour = -6.0;

    // ── En-route charging fields ─────────────────────────────────────────────

    private boolean enableEnRouteCharging = false;

    @PositiveOrZero
    private double enRouteSearchRadius = 2000.0;

    @PositiveOrZero
    private double enRouteSafetyBuffer = 0.10;

    @PositiveOrZero
    private double socProblemThreshold = 0.05;

    // ── Heterogeneity fields ─────────────────────────────────────────────────

    private boolean usePersonLevelParams = false;

    // ── Smart charging fields ────────────────────────────────────────────────

    @PositiveOrZero
    private double alphaScaleTemporal = 1.0;

    private boolean enableSmartCharging = false;
    private double awarenessFactor = 0.0;
    private double coincidenceFactor = 0.0;


    // ═════════════════════════════════════════════════════════════════════════
    //  Constructor
    // ═════════════════════════════════════════════════════════════════════════

    public UrbanEVConfigGroup() {
        super(GROUP_NAME);
    }

    /**
     * Called by MATSim after parameter map is populated from XML.
     * Check for deprecated parameter names and warn.
     */
    @Override
    public void checkConsistency(org.matsim.core.config.Config config) {
        super.checkConsistency(config);
        // Detect deprecated publicChargingCost from old config files
        Map<String, String> params = this.getParams();
        if (params.containsKey("publicChargingCost")) {
            double oldVal = Double.parseDouble(params.get("publicChargingCost"));
            log.warn("UrbanEVConfigGroup: DEPRECATED parameter 'publicChargingCost' found (value=" + oldVal + "). "
                    + "This has been replaced by 'publicL1Cost', 'publicL2Cost', and 'publicDCFCCost'. "
                    + "The old value will be used as a fallback for all three tiers if the new parameters are at their defaults.");
            if (publicL1Cost == 0.18 && publicL2Cost == 0.25 && publicDCFCCost == 0.48) {
                // New params still at defaults — apply old value as uniform fallback
                publicL1Cost = oldVal;
                publicL2Cost = oldVal;
                publicDCFCCost = oldVal;
            }
        }
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Comments for config file generation
    // ═════════════════════════════════════════════════════════════════════════

    @Override
    public Map<String, String> getComments() {
        Map<String, String> map = super.getComments();
        map.put(RANGE_ANXIETY_UTILITY, RANGE_ANXIETY_UTILITY_EXP);
        map.put(EMPTY_BATTERY_UTILITY, EMPTY_BATTERY_UTILITY_EXP);
        map.put(WALKING_UTILITY, WALKING_UTILITY_EXP);
        map.put(HOME_CHARGING_UTILITY, HOME_CHARGING_UTILITY_EXP);
        map.put(SOC_DIFFERENCE_UTILITY, SOC_DIFFERENCE_UTILITY_EXP);
        map.put(VEHICLE_TYPES_FILE, VEHICLE_TYPES_FILE_EXP);
        map.put(PARKING_SEARCH_RADIUS, PARKING_SEARCH_RADIUS_EXP);
        map.put(DEFAULT_RANGE_ANXIETY_THRESHOLD, DEFAULT_RANGE_ANXIETY_THRESHOLD_EXP);
        map.put(MAXNUMBERSIMULTANEOUSPLANCHANGES, MAXNUMBERSIMULTANEOUSPLANCHANGES_EXP);
        map.put(TIMEADJUSTMENTPROBABILITY, TIMEADJUSTMENTPROBABILITY_EXP);
        map.put(MAXTIMEFLEXIBILITY, MAXTIMEFLEXIBILITY_EXP);
        map.put(GENERATE_HOME_CHARGERS_BY_PERCENTAGE, GENERATE_HOME_CHARGERS_BY_PERCENTAGE_EXP);
        map.put(GENERATE_WORK_CHARGERS_BY_PERCENTAGE, GENERATE_WORK_CHARGERS_BY_PERCENTAGE_EXP);
        map.put(HOME_CHARGER_PERCENTAGE, HOME_CHARGER_PERCENTAGE_EXP);
        map.put(WORK_CHARGER_PERCENTAGE, WORK_CHARGER_PERCENTAGE_EXP);
        map.put(DEFAULT_HOME_CHARGER_POWER, DEFAULT_HOME_CHARGER_POWER_EXP);
        map.put(DEFAULT_WORK_CHARGER_POWER, DEFAULT_WORK_CHARGER_POWER_EXP);

        // Charging cost parameters
        map.put(HOME_CHARGING_COST, HOME_CHARGING_COST_EXP);
        map.put(WORK_CHARGING_COST, WORK_CHARGING_COST_EXP);
        map.put(PUBLIC_L1_COST, PUBLIC_L1_COST_EXP);
        map.put(PUBLIC_L2_COST, PUBLIC_L2_COST_EXP);
        map.put(PUBLIC_DCFC_COST, PUBLIC_DCFC_COST_EXP);
        map.put(L2_POWER_THRESHOLD, L2_POWER_THRESHOLD_EXP);
        map.put(DCFC_POWER_THRESHOLD, DCFC_POWER_THRESHOLD_EXP);
        map.put(BETA_MONEY, BETA_MONEY_EXP);
        map.put(ALPHA_SCALE_COST, ALPHA_SCALE_COST_EXP);

        // VoT parameters
        map.put(BASE_VALUE_OF_TIME_FACTOR, BASE_VALUE_OF_TIME_FACTOR_EXP);
        map.put(QUEUE_ANNOYANCE_FACTOR, QUEUE_ANNOYANCE_FACTOR_EXP);
        map.put(DETOUR_DISUTILITY_PER_HOUR, DETOUR_DISUTILITY_PER_HOUR_EXP);

        // En-route charging parameters
        map.put(ENABLE_EN_ROUTE_CHARGING, ENABLE_EN_ROUTE_CHARGING_EXP);
        map.put(EN_ROUTE_SEARCH_RADIUS, EN_ROUTE_SEARCH_RADIUS_EXP);
        map.put(EN_ROUTE_SAFETY_BUFFER, EN_ROUTE_SAFETY_BUFFER_EXP);
        map.put(SOC_PROBLEM_THRESHOLD, SOC_PROBLEM_THRESHOLD_EXP);

        // Heterogeneity
        map.put(USE_PERSON_LEVEL_PARAMS, USE_PERSON_LEVEL_PARAMS_EXP);

        // Smart charging
        map.put(ENABLE_SMART_CHARGING, "Enable smart charging behavior: delayed start times, ToU awareness, and coincidence effect.");
        map.put(COINCIDENCE_FACTOR, "Probability that multiple rescheduled charging events start at the same time in the shifted low-ToU window.");
        map.put(AWARENESS_FACTOR, "Probability [0.0-1.0] of an agent being aware of ToU pricing and willing to shift charging start.");
        map.put(ALPHA_SCALE_TEMPORAL, "Temporal preference index in [0,2]. 0 biases shifted charging near start of low-ToU; "
                + "2 biases near end of low-ToU; 1 biases mid-window.");

        return map;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Replanning
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(MAXNUMBERSIMULTANEOUSPLANCHANGES)
    public int getMaxNumberSimultaneousPlanChanges() {
        return maxNumberSimultaneousPlanChanges;
    }

    @StringSetter(MAXNUMBERSIMULTANEOUSPLANCHANGES)
    public void setMaxNumberSimultaneousPlanChanges(int maxNumberSimultaneousPlanChanges) {
        this.maxNumberSimultaneousPlanChanges = maxNumberSimultaneousPlanChanges;
    }

    @StringGetter(TIMEADJUSTMENTPROBABILITY)
    public Double getTimeAdjustmentProbability() {
        return timeAdjustmentProbability;
    }

    @StringSetter(TIMEADJUSTMENTPROBABILITY)
    public void setTimeAdjustmentProbability(Double timeAdjustmentProbability) {
        this.timeAdjustmentProbability = timeAdjustmentProbability;
    }

    @StringGetter(MAXTIMEFLEXIBILITY)
    public int getMaxTimeFlexibility() {
        return maxTimeFlexibility;
    }

    @StringSetter(MAXTIMEFLEXIBILITY)
    public void setMaxTimeFlexibility(int maxTimeFlexibility) {
        this.maxTimeFlexibility = maxTimeFlexibility;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Scoring utilities
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(RANGE_ANXIETY_UTILITY)
    public double getRangeAnxietyUtility() { return rangeAnxietyUtility; }

    @StringSetter(RANGE_ANXIETY_UTILITY)
    public void setRangeAnxietyUtility(double rangeAnxietyUtility) { this.rangeAnxietyUtility = rangeAnxietyUtility; }

    @StringGetter(EMPTY_BATTERY_UTILITY)
    public double getEmptyBatteryUtility() { return emptyBatteryUtility; }

    @StringSetter(EMPTY_BATTERY_UTILITY)
    public void setEmptyBatteryUtility(double emptyBatteryUtility) { this.emptyBatteryUtility = emptyBatteryUtility; }

    @StringGetter(WALKING_UTILITY)
    public double getWalkingUtility() { return walkingUtility; }

    @StringSetter(WALKING_UTILITY)
    public void setWalkingUtility(double walkingUtility) { this.walkingUtility = walkingUtility; }

    @StringGetter(HOME_CHARGING_UTILITY)
    public double getHomeChargingUtility() { return homeChargingUtility; }

    @StringSetter(HOME_CHARGING_UTILITY)
    public void setHomeChargingUtility(double homeChargingUtility) { this.homeChargingUtility = homeChargingUtility; }

    @StringGetter(SOC_DIFFERENCE_UTILITY)
    public double getSocDifferenceUtility() { return socDifferenceUtility; }

    @StringSetter(SOC_DIFFERENCE_UTILITY)
    public void setSocDifferenceUtility(double socDifferenceUtility) { this.socDifferenceUtility = socDifferenceUtility; }

    @StringGetter(DEFAULT_RANGE_ANXIETY_THRESHOLD)
    public double getDefaultRangeAnxietyThreshold() {
        return defaultRangeAnxietyThreshold;
    }

    @StringSetter(DEFAULT_RANGE_ANXIETY_THRESHOLD)
    public void setDefaultRangeAnxietyThreshold(double defaultRangeAnxietyThreshold) {
        this.defaultRangeAnxietyThreshold = defaultRangeAnxietyThreshold;
    }

    @StringGetter(VEHICLE_TYPES_FILE)
    public String getVehicleTypesFile() {
        return vehicleTypesFile;
    }

    @StringSetter(VEHICLE_TYPES_FILE)
    public void setVehicleTypesFile(String vehicleTypesFile) {
        this.vehicleTypesFile = vehicleTypesFile;
    }

    @StringGetter(PARKING_SEARCH_RADIUS)
    public int getParkingSearchRadius() {
        return parkingSearchRadius;
    }

    @StringSetter(PARKING_SEARCH_RADIUS)
    public void setParkingSearchRadius(int parkingSearchRadius) {
        this.parkingSearchRadius = parkingSearchRadius;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Charger generation
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(GENERATE_HOME_CHARGERS_BY_PERCENTAGE)
    public boolean isGenerateHomeChargersByPercentage() {
        return generateHomeChargersByPercentage;
    }

    @StringSetter(GENERATE_HOME_CHARGERS_BY_PERCENTAGE)
    public void setGenerateHomeChargersByPercentage(boolean generateHomeChargersByPercentage) {
        this.generateHomeChargersByPercentage = generateHomeChargersByPercentage;
    }

    @StringGetter(GENERATE_WORK_CHARGERS_BY_PERCENTAGE)
    public boolean isGenerateWorkChargersByPercentage() {
        return generateWorkChargersByPercentage;
    }

    @StringSetter(GENERATE_WORK_CHARGERS_BY_PERCENTAGE)
    public void setGenerateWorkChargersByPercentage(boolean generateWorkChargersByPercentage) {
        this.generateWorkChargersByPercentage = generateWorkChargersByPercentage;
    }

    @StringGetter(HOME_CHARGER_PERCENTAGE)
    public double getHomeChargerPercentage() {
        return homeChargerPercentage;
    }

    @StringSetter(HOME_CHARGER_PERCENTAGE)
    public void setHomeChargerPercentage(double homeChargerPercentage) {
        this.homeChargerPercentage = homeChargerPercentage;
    }

    @StringGetter(WORK_CHARGER_PERCENTAGE)
    public double getWorkChargerPercentage() {
        return workChargerPercentage;
    }

    @StringSetter(WORK_CHARGER_PERCENTAGE)
    public void setWorkChargerPercentage(double workChargerPercentage) {
        this.workChargerPercentage = workChargerPercentage;
    }

    @StringGetter(DEFAULT_HOME_CHARGER_POWER)
    public double getDefaultHomeChargerPower() {
        return defaultHomeChargerPower;
    }

    @StringSetter(DEFAULT_HOME_CHARGER_POWER)
    public void setDefaultHomeChargerPower(double defaultHomeChargerPower) {
        this.defaultHomeChargerPower = defaultHomeChargerPower;
    }

    @StringGetter(DEFAULT_WORK_CHARGER_POWER)
    public double getDefaultWorkChargerPower() {
        return defaultWorkChargerPower;
    }

    @StringSetter(DEFAULT_WORK_CHARGER_POWER)
    public void setDefaultWorkChargerPower(double defaultWorkChargerPower) {
        this.defaultWorkChargerPower = defaultWorkChargerPower;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Charging costs (power-tier pricing)
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(HOME_CHARGING_COST)
    public double getHomeChargingCost() {
        return homeChargingCost;
    }

    @StringSetter(HOME_CHARGING_COST)
    public void setHomeChargingCost(double homeChargingCost) {
        this.homeChargingCost = homeChargingCost;
    }

    @StringGetter(WORK_CHARGING_COST)
    public double getWorkChargingCost() {
        return workChargingCost;
    }

    @StringSetter(WORK_CHARGING_COST)
    public void setWorkChargingCost(double workChargingCost) {
        this.workChargingCost = workChargingCost;
    }

    @StringGetter(PUBLIC_L1_COST)
    public double getPublicL1Cost() {
        return publicL1Cost;
    }

    @StringSetter(PUBLIC_L1_COST)
    public void setPublicL1Cost(double publicL1Cost) {
        this.publicL1Cost = publicL1Cost;
    }

    @StringGetter(PUBLIC_L2_COST)
    public double getPublicL2Cost() {
        return publicL2Cost;
    }

    @StringSetter(PUBLIC_L2_COST)
    public void setPublicL2Cost(double publicL2Cost) {
        this.publicL2Cost = publicL2Cost;
    }

    @StringGetter(PUBLIC_DCFC_COST)
    public double getPublicDCFCCost() {
        return publicDCFCCost;
    }

    @StringSetter(PUBLIC_DCFC_COST)
    public void setPublicDCFCCost(double publicDCFCCost) {
        this.publicDCFCCost = publicDCFCCost;
    }

    @StringGetter(L2_POWER_THRESHOLD)
    public double getL2PowerThreshold() {
        return l2PowerThreshold;
    }

    @StringSetter(L2_POWER_THRESHOLD)
    public void setL2PowerThreshold(double l2PowerThreshold) {
        this.l2PowerThreshold = l2PowerThreshold;
    }

    @StringGetter(DCFC_POWER_THRESHOLD)
    public double getDcfcPowerThreshold() {
        return dcfcPowerThreshold;
    }

    @StringSetter(DCFC_POWER_THRESHOLD)
    public void setDcfcPowerThreshold(double dcfcPowerThreshold) {
        this.dcfcPowerThreshold = dcfcPowerThreshold;
    }

    @StringGetter(BETA_MONEY)
    public double getBetaMoney() {
        return betaMoney;
    }

    @StringSetter(BETA_MONEY)
    public void setBetaMoney(double betaMoney) {
        this.betaMoney = betaMoney;
    }

    @StringGetter(ALPHA_SCALE_COST)
    public double getAlphaScaleCost() {
        return alphaScaleCost;
    }

    @StringSetter(ALPHA_SCALE_COST)
    public void setAlphaScaleCost(double alphaScaleCost) {
        this.alphaScaleCost = alphaScaleCost;
    }

    /**
     * @deprecated Use {@link #getPublicChargingCostForPower(double)} or the individual
     * tier getters (getPublicL1Cost, getPublicL2Cost, getPublicDCFCCost) instead.
     * Returns L2 cost as a backward-compatible default.
     */
    @Deprecated
    public double getPublicChargingCost() {
        return publicL2Cost;
    }

    /**
     * Convenience method: returns the public charging cost for a given charger power in kW.
     * Uses l2PowerThreshold and dcfcPowerThreshold to classify into L1/L2/DCFC tiers.
     */
    public double getPublicChargingCostForPower(double chargerPowerKw) {
        if (chargerPowerKw >= dcfcPowerThreshold) {
            return publicDCFCCost;
        } else if (chargerPowerKw >= l2PowerThreshold) {
            return publicL2Cost;
        } else {
            return publicL1Cost;
        }
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Value of Time
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(BASE_VALUE_OF_TIME_FACTOR)
    public double getBaseValueOfTimeFactor() {
        return baseValueOfTimeFactor;
    }

    @StringSetter(BASE_VALUE_OF_TIME_FACTOR)
    public void setBaseValueOfTimeFactor(double baseValueOfTimeFactor) {
        this.baseValueOfTimeFactor = baseValueOfTimeFactor;
    }

    @StringGetter(QUEUE_ANNOYANCE_FACTOR)
    public double getQueueAnnoyanceFactor() {
        return queueAnnoyanceFactor;
    }

    @StringSetter(QUEUE_ANNOYANCE_FACTOR)
    public void setQueueAnnoyanceFactor(double queueAnnoyanceFactor) {
        this.queueAnnoyanceFactor = queueAnnoyanceFactor;
    }

    @StringGetter(DETOUR_DISUTILITY_PER_HOUR)
    public double getDetourDisutilityPerHour() {
        return detourDisutilityPerHour;
    }

    @StringSetter(DETOUR_DISUTILITY_PER_HOUR)
    public void setDetourDisutilityPerHour(double detourDisutilityPerHour) {
        this.detourDisutilityPerHour = detourDisutilityPerHour;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — En-route charging
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(ENABLE_EN_ROUTE_CHARGING)
    public boolean isEnableEnRouteCharging() {
        return enableEnRouteCharging;
    }

    @StringSetter(ENABLE_EN_ROUTE_CHARGING)
    public void setEnableEnRouteCharging(boolean enableEnRouteCharging) {
        this.enableEnRouteCharging = enableEnRouteCharging;
    }

    @StringGetter(EN_ROUTE_SEARCH_RADIUS)
    public double getEnRouteSearchRadius() {
        return enRouteSearchRadius;
    }

    @StringSetter(EN_ROUTE_SEARCH_RADIUS)
    public void setEnRouteSearchRadius(double enRouteSearchRadius) {
        this.enRouteSearchRadius = enRouteSearchRadius;
    }

    @StringGetter(EN_ROUTE_SAFETY_BUFFER)
    public double getEnRouteSafetyBuffer() {
        return enRouteSafetyBuffer;
    }

    @StringSetter(EN_ROUTE_SAFETY_BUFFER)
    public void setEnRouteSafetyBuffer(double enRouteSafetyBuffer) {
        this.enRouteSafetyBuffer = enRouteSafetyBuffer;
    }

    @StringGetter(SOC_PROBLEM_THRESHOLD)
    public double getSocProblemThreshold() {
        return socProblemThreshold;
    }

    @StringSetter(SOC_PROBLEM_THRESHOLD)
    public void setSocProblemThreshold(double socProblemThreshold) {
        this.socProblemThreshold = socProblemThreshold;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Heterogeneity
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(USE_PERSON_LEVEL_PARAMS)
    public boolean isUsePersonLevelParams() {
        return usePersonLevelParams;
    }

    @StringSetter(USE_PERSON_LEVEL_PARAMS)
    public void setUsePersonLevelParams(boolean usePersonLevelParams) {
        this.usePersonLevelParams = usePersonLevelParams;
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Getters and Setters — Smart charging
    // ═════════════════════════════════════════════════════════════════════════

    @StringGetter(ENABLE_SMART_CHARGING)
    public boolean isEnableSmartCharging() {
        return enableSmartCharging;
    }

    @StringSetter(ENABLE_SMART_CHARGING)
    public void setEnableSmartCharging(boolean enableSmartCharging) {
        this.enableSmartCharging = enableSmartCharging;
    }

    @StringSetter(AWARENESS_FACTOR)
    public void setAwarenessFactor(double awarenessFactor) {
        if (awarenessFactor < 0.0 || awarenessFactor > 1.0) {
            log.warn("UrbanEVConfigGroup: awarenessFactor outside [0,1] (" + awarenessFactor + "), clamping.");
        }
        this.awarenessFactor = Math.max(0.0, Math.min(1.0, awarenessFactor));
    }

    @StringSetter(COINCIDENCE_FACTOR)
    public void setCoincidenceFactor(double coincidenceFactor) {
        if (coincidenceFactor < 0.0 || coincidenceFactor > 1.0) {
            log.warn("UrbanEVConfigGroup: coincidenceFactor outside [0,1] (" + coincidenceFactor + "), clamping.");
        }
        this.coincidenceFactor = Math.max(0.0, Math.min(1.0, coincidenceFactor));
    }

    @StringGetter(AWARENESS_FACTOR)
    public double getAwarenessFactor() {
        return awarenessFactor;
    }

    @StringGetter(COINCIDENCE_FACTOR)
    public double getCoincidenceFactor() {
        return coincidenceFactor;
    }

    @StringGetter(ALPHA_SCALE_TEMPORAL)
    public double getAlphaScaleTemporal() {
        return alphaScaleTemporal;
    }

    @StringSetter(ALPHA_SCALE_TEMPORAL)
    public void setAlphaScaleTemporal(double v) {
        if (!Double.isFinite(v)) {
            log.warn("UrbanEVConfigGroup: alphaScaleTemporal is not finite (" + v + "), using 1.0.");
            this.alphaScaleTemporal = 1.0;
            return;
        }
        if (v < 0.0) {
            log.warn("UrbanEVConfigGroup: alphaScaleTemporal < 0 (" + v + "), clamping to 0.0.");
            this.alphaScaleTemporal = 0.0;
        } else if (v > 2.0) {
            log.warn("UrbanEVConfigGroup: alphaScaleTemporal > 2 (" + v + "), clamping to 2.0.");
            this.alphaScaleTemporal = 2.0;
        } else {
            this.alphaScaleTemporal = v;
        }
    }


    // ═════════════════════════════════════════════════════════════════════════
    //  Sanity checks
    // ═════════════════════════════════════════════════════════════════════════

    public void logIfSuspicious() {
        if (betaMoney > 0.0) {
            log.warn("UrbanEVConfigGroup: betaMoney > 0.0 detected (" + betaMoney + "). "
                    + "EV charging cost will increase utility; is that really intended?");
        }
        if (homeChargingCost < 0.0 || workChargingCost < 0.0
                || publicL1Cost < 0.0 || publicL2Cost < 0.0 || publicDCFCCost < 0.0) {
            log.error("UrbanEVConfigGroup: negative charging cost detected. "
                    + "Please check home/work/publicL1/publicL2/publicDCFC cost in config.xml.");
        }
        if (publicDCFCCost < publicL2Cost) {
            log.warn("UrbanEVConfigGroup: publicDCFCCost (" + publicDCFCCost
                    + ") < publicL2Cost (" + publicL2Cost + "). "
                    + "DCFC is typically more expensive than L2. Check pricing tiers.");
        }
        if (publicL2Cost < publicL1Cost) {
            log.warn("UrbanEVConfigGroup: publicL2Cost (" + publicL2Cost
                    + ") < publicL1Cost (" + publicL1Cost + "). "
                    + "L2 is typically more expensive than L1. Check pricing tiers.");
        }
        if (l2PowerThreshold >= dcfcPowerThreshold) {
            log.error("UrbanEVConfigGroup: l2PowerThreshold (" + l2PowerThreshold
                    + ") >= dcfcPowerThreshold (" + dcfcPowerThreshold + "). "
                    + "L2 threshold must be less than DCFC threshold.");
        }
        if (enRouteSafetyBuffer < 0.0 || enRouteSafetyBuffer > 0.5) {
            log.warn("UrbanEVConfigGroup: enRouteSafetyBuffer (" + enRouteSafetyBuffer
                    + ") outside typical range [0.0, 0.5].");
        }
        if (socProblemThreshold > defaultRangeAnxietyThreshold) {
            log.warn("UrbanEVConfigGroup: socProblemThreshold (" + socProblemThreshold
                    + ") > defaultRangeAnxietyThreshold (" + defaultRangeAnxietyThreshold
                    + "). Problem threshold should be below anxiety threshold.");
        }
        if (detourDisutilityPerHour > 0.0) {
            log.warn("UrbanEVConfigGroup: detourDisutilityPerHour > 0.0 (" + detourDisutilityPerHour
                    + "). Detours should have negative utility.");
        }
    }
}
