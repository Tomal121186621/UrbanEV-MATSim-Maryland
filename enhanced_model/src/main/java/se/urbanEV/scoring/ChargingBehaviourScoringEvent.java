package se.urbanEV.scoring;

import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.Event;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.api.internal.HasPersonId;

import java.util.Map;

public class ChargingBehaviourScoringEvent extends Event implements HasPersonId {
    public static final String EVENT_TYPE = "scoring";

    private final Id<Person> personId;
    private final Double soc;
    private final Double walkingDistance;
    private final String activityType;
    private final Double startSoc;

    // OmkarP.(2025): charging cost fields
    private final Double energyChargedKWh;
    private final String chargerType;      // "home" / "work" / "public"
    private final boolean costOnly;
    private final Double pricingTime;

    // Power-tier pricing
    private final Double chargerPowerKw;   // kW output of the plug; null when not reported

    // En-route charging overhead (null when not applicable)
    private final Double detourSeconds;    // extra travel time incurred by the en-route detour
    private final Double queueWaitSeconds; // time spent waiting for a free charger plug

    // -------------------------------------------------------------------------
    // Constructors — each shorter one delegates to the full 13-param constructor
    // -------------------------------------------------------------------------

    /** Backward-compatible constructor (no cost info): OmkarP.(2025) */
    public ChargingBehaviourScoringEvent(double time,
                                         Id<Person> personId,
                                         Double soc,
                                         Double walkingDistance,
                                         String activityType,
                                         double startSoc) {
        this(time, personId, soc, walkingDistance, activityType, startSoc,
                null, null, null, false, null, null, null);
    }

    /** Constructor with charging cost info: OmkarP.(2025) */
    public ChargingBehaviourScoringEvent(double time,
                                         Id<Person> personId,
                                         Double soc,
                                         Double walkingDistance,
                                         String activityType,
                                         double startSoc,
                                         Double pricingTime,
                                         Double energyChargedKWh,
                                         String chargerType,
                                         boolean costOnly) {
        this(time, personId, soc, walkingDistance, activityType, startSoc,
                pricingTime, energyChargedKWh, chargerType, costOnly, null, null, null);
    }

    /** Constructor with charger plug power for power-tier pricing. */
    public ChargingBehaviourScoringEvent(double time,
                                         Id<Person> personId,
                                         Double soc,
                                         Double walkingDistance,
                                         String activityType,
                                         double startSoc,
                                         Double pricingTime,
                                         Double energyChargedKWh,
                                         String chargerType,
                                         boolean costOnly,
                                         Double chargerPowerKw) {
        this(time, personId, soc, walkingDistance, activityType, startSoc,
                pricingTime, energyChargedKWh, chargerType, costOnly, chargerPowerKw, null, null);
    }

    /**
     * Full constructor (13 params).
     *
     * @param chargerPowerKw   kW output of the plug; null when not reported
     * @param detourSeconds    extra travel time from en-route detour; null when not applicable
     * @param queueWaitSeconds time waiting for a free plug; null when not applicable
     */
    public ChargingBehaviourScoringEvent(double time,
                                         Id<Person> personId,
                                         Double soc,
                                         Double walkingDistance,
                                         String activityType,
                                         double startSoc,
                                         Double pricingTime,
                                         Double energyChargedKWh,
                                         String chargerType,
                                         boolean costOnly,
                                         Double chargerPowerKw,
                                         Double detourSeconds,
                                         Double queueWaitSeconds) {
        super(time);
        this.personId = personId;
        this.soc = soc;
        this.walkingDistance = walkingDistance;
        this.activityType = activityType;
        this.startSoc = startSoc;

        this.pricingTime = pricingTime;
        this.energyChargedKWh = energyChargedKWh;
        this.chargerType = chargerType;
        this.costOnly = costOnly;

        this.chargerPowerKw = chargerPowerKw;
        this.detourSeconds = detourSeconds;
        this.queueWaitSeconds = queueWaitSeconds;
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------

    @Override
    public Id<Person> getPersonId()      { return personId; }
    @Override
    public String getEventType()         { return EVENT_TYPE; }

    public Double getSoc()               { return soc; }
    public Double getWalkingDistance()   { return walkingDistance; }
    public String getActivityType()      { return activityType; }
    public Double getStartSoc()          { return startSoc; }

    // OmkarP.(2025)
    public Double getPricingTime()       { return pricingTime; }
    public Double getEnergyChargedKWh()  { return energyChargedKWh; }
    public String getChargerType()       { return chargerType; }
    public boolean isCostOnly()          { return costOnly; }

    /** kW output of the charging plug; null when not reported. Used for power-tier pricing. */
    public Double getChargerPowerKw()    { return chargerPowerKw; }

    /** Extra travel time (seconds) incurred by an en-route charging detour; null when not applicable. */
    public Double getDetourSeconds()     { return detourSeconds; }

    /** Time (seconds) the agent spent waiting for a free charger plug; null when not applicable. */
    public Double getQueueWaitSeconds()  { return queueWaitSeconds; }

    // -------------------------------------------------------------------------
    // Event attributes (for event-file serialisation)
    // -------------------------------------------------------------------------

    @Override
    public Map<String, String> getAttributes() {
        Map<String, String> attributes = super.getAttributes();

        if (soc != null)              { attributes.put("soc",              soc.toString()); }
        if (walkingDistance != null)  { attributes.put("walkingDistance",  walkingDistance.toString()); }
        if (activityType != null)     { attributes.put("activityType",     activityType); }
        if (startSoc != null)         { attributes.put("startSoc",         startSoc.toString()); }

        if (energyChargedKWh != null) { attributes.put("energyChargedKWh", energyChargedKWh.toString()); }
        if (chargerType != null)      { attributes.put("chargerType",      chargerType); }
        if (pricingTime != null)      { attributes.put("pricingTime",      pricingTime.toString()); }
        attributes.put("costOnly",    Boolean.toString(costOnly));

        if (chargerPowerKw != null)   { attributes.put("chargerPowerKw",   chargerPowerKw.toString()); }
        if (detourSeconds != null)    { attributes.put("detourSeconds",    detourSeconds.toString()); }
        if (queueWaitSeconds != null) { attributes.put("queueWaitSeconds", queueWaitSeconds.toString()); }

        return attributes;
    }
}
