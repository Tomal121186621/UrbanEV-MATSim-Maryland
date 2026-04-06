/*
File originally created, published and licensed by contributors of the org.matsim.* project.
Please consider the original license notice below.
This is a modified version of the original source code!

Modified 2020 by Lennart Adenaw, Technical University Munich, Chair of Automotive Technology
email	:	lennart.adenaw@tum.de
*/

/* ORIGINAL LICENSE
 *  *********************************************************************** *
 * project: org.matsim.*
 *                                                                         *
 * *********************************************************************** *
 *                                                                         *
 * copyright       : (C) 2016 by the members listed in the COPYING,        *
 *                   LICENSE and WARRANTY file.                            *
 * email           : info at matsim dot org                                *
 *                                                                         *
 * *********************************************************************** *
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *   See also COPYING, LICENSE and WARRANTY file                           *
 *                                                                         *
 * *********************************************************************** */

package se.urbanEV.charging;
/*
 * created by jbischoff, 09.10.2018
 *  This is an events based approach to trigger vehicle charging. Vehicles will be charged as soon as a person begins a charging activity.
 */

import org.matsim.core.config.Config;
import se.urbanEV.MobsimScopeEventHandling;
import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.fleet.ElectricFleet;
import se.urbanEV.fleet.ElectricVehicle;
import se.urbanEV.infrastructure.Charger;
import se.urbanEV.infrastructure.ChargingInfrastructure;
import se.urbanEV.scoring.ChargingBehaviourScoringEvent;
import org.apache.log4j.Logger;
import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.ActivityEndEvent;
import org.matsim.api.core.v01.events.ActivityStartEvent;
import org.matsim.api.core.v01.events.PersonLeavesVehicleEvent;
import org.matsim.api.core.v01.events.handler.ActivityEndEventHandler;
import org.matsim.api.core.v01.events.handler.ActivityStartEventHandler;
import org.matsim.api.core.v01.events.handler.PersonLeavesVehicleEventHandler;
import org.matsim.api.core.v01.network.Network;
import org.matsim.api.core.v01.population.Activity;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.PlanElement;
import org.matsim.api.core.v01.population.Population;
import org.matsim.contrib.ev.MobsimScopeEventHandler;
import org.matsim.contrib.util.PartialSort;
import org.matsim.contrib.util.distance.DistanceUtils;
import org.matsim.core.api.experimental.events.EventsManager;
import org.matsim.vehicles.Vehicle;

import javax.inject.Inject;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class VehicleChargingHandler
        implements ActivityStartEventHandler, ActivityEndEventHandler, PersonLeavesVehicleEventHandler,
        ChargingEndEventHandler, MobsimScopeEventHandler {

    private static final Logger log = Logger.getLogger(VehicleChargingHandler.class);

    public static final String CHARGING_IDENTIFIER = " charging";

    /** Expected wait time (seconds) when all compatible chargers in radius are occupied. */
    private static final double ESTIMATED_QUEUE_WAIT_SEC = 900.0; // 15 minutes

    private Map<Id<Person>, Id<Vehicle>> lastVehicleUsed = new HashMap<>();
    private Map<Id<ElectricVehicle>, Id<Charger>> vehiclesAtChargers = new HashMap<>();

    // track SOC and time at the start of each charging session — for smart rescheduling
    private final Map<Id<ElectricVehicle>, Double> chargeStartSoc  = new HashMap<>();
    private final Map<Id<ElectricVehicle>, Double> chargeStartTime = new HashMap<>();

    // plug power (kW) stored when a charger is assigned, consumed in ActivityEndEvent
    private final Map<Id<ElectricVehicle>, Double> chargerPlugPowerKW = new HashMap<>();

    // estimated queue wait (seconds) when all chargers in radius are full
    private final Map<Id<ElectricVehicle>, Double> queueWaitTime = new HashMap<>();

    private final ChargingInfrastructure chargingInfrastructure;
    private final Network network;
    private final ElectricFleet electricFleet;
    private final Population population;
    private final int parkingSearchRadius;
    private final EventsManager eventsManager;
    private final double qsimEndTime;

    // scheduler for smart charging: OmkarP.(2025)
    private final UrbanEVConfigGroup urbanEvCfg;
    private final SmartChargingScheduler smartScheduler;

    @Inject
    public VehicleChargingHandler(ChargingInfrastructure chargingInfrastructure,
                                  Network network,
                                  ElectricFleet electricFleet,
                                  Population population,
                                  EventsManager eventsManager,
                                  MobsimScopeEventHandling events,
                                  UrbanEVConfigGroup urbanEVCfg,
                                  Config config) {
        this.chargingInfrastructure = chargingInfrastructure;
        this.network = network;
        this.electricFleet = electricFleet;
        this.population = population;
        this.eventsManager = eventsManager;
        this.parkingSearchRadius = urbanEVCfg.getParkingSearchRadius();
        this.urbanEvCfg = urbanEVCfg;

        this.qsimEndTime = config.qsim().getEndTime().seconds();
        this.smartScheduler = new SmartChargingScheduler(chargingInfrastructure, electricFleet, this);
        events.addMobsimScopeHandler(this);
    }

    // -------------------------------------------------------------------------
    // SmartChargingScheduler callback
    // -------------------------------------------------------------------------

    /**
     * Called by SmartChargingScheduler when a deferred home-charging session plugs in.
     * Registers start SOC/time and charger power so ActivityEndEvent can compute costs.
     */
    public void onSmartChargePlugged(Id<ElectricVehicle> evId, Id<Charger> chargerId, double time) {
        ElectricVehicle ev = electricFleet.getElectricVehicles().get(evId);
        if (ev == null) {
            log.warn("onSmartChargePlugged: EV " + evId + " not found in fleet at t=" + time);
            return;
        }

        vehiclesAtChargers.put(evId, chargerId);

        double socFraction = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
        chargeStartSoc.put(evId, socFraction);
        chargeStartTime.put(evId, time);

        // Store charger plug power at the moment of plug-in
        Charger charger = chargingInfrastructure.getChargers().get(chargerId);
        if (charger != null) {
            chargerPlugPowerKW.put(evId, charger.getPlugPower() / 1000.0);
        }

        if (log.isDebugEnabled()) {
            log.debug(String.format(
                    "onSmartChargePlugged: EV %s plugged at charger %s at t=%.0f, soc=%.3f",
                    evId, chargerId, time, socFraction
            ));
        }
    }

    // -------------------------------------------------------------------------
    // ActivityStartEvent — charging activity begins
    // -------------------------------------------------------------------------

    @Override
    public void handleEvent(ActivityStartEvent event) {
        String actType = event.getActType();
        Id<Person> personId = event.getPersonId();
        Id<Vehicle> vehicleId = lastVehicleUsed.get(personId);
        if (vehicleId != null) {
            Id<ElectricVehicle> evId = Id.create(vehicleId, ElectricVehicle.class);
            if (electricFleet.getElectricVehicles().containsKey(evId)) {
                ElectricVehicle ev = electricFleet.getElectricVehicles().get(evId);
                Person person = population.getPersons().get(personId);
                double walkingDistance = 0.0;

                if (event.getActType().endsWith(CHARGING_IDENTIFIER)) {
                    Activity activity = getActivity(person, event.getTime());
                    Coord activityCoord = activity != null
                            ? activity.getCoord()
                            : network.getLinks().get(event.getLinkId()).getCoord();
                    Charger selectedCharger = findBestCharger(activityCoord, ev);

                    if (selectedCharger != null) {
                        boolean isHomeChargingAct =
                                actType.startsWith("home") && actType.endsWith(CHARGING_IDENTIFIER);

                        // default: immediate charging (for non-home or smart disabled)
                        boolean smartEnabled = urbanEvCfg.isEnableSmartCharging() && isHomeChargingAct;

                        // Smart ToU-aware rescheduling: OmkarP.(2025)
                        if (smartEnabled && activity != null) {
                            double arrivalTime = event.getTime();

                            double departureTime;
                            if (activity.getEndTime().isDefined()) {
                                departureTime = activity.getEndTime().seconds();
                            } else {
                                departureTime = qsimEndTime;
                            }

                            if (departureTime > arrivalTime) {
                                // energy missing (J → kWh)
                                double energyRequiredJ = ev.getBattery().getCapacity() - ev.getBattery().getSoc();
                                if (energyRequiredJ < 0.0) energyRequiredJ = 0.0;
                                double energyRequiredKWh = energyRequiredJ / 3_600_000.0;

                                // Approximate charging duration using person's home charger power
                                double powerKW = urbanEvCfg.getDefaultHomeChargerPower();
                                Object pHomeP = person.getAttributes().getAttribute("homeChargerPower");
                                if (pHomeP != null) {
                                    try { powerKW = Double.parseDouble(pHomeP.toString()); }
                                    catch (Exception ignored) { }
                                }

                                double effectiveKW    = Math.max(0.1, 0.85 * powerKW);
                                double chargingDuration = (energyRequiredKWh / effectiveKW) * 3600.0;
                                double maxDur           = Math.max(0.0, departureTime - arrivalTime);
                                chargingDuration = Math.min(chargingDuration, maxDur);

                                Object awareAttr = person.getAttributes().getAttribute("smartChargingAware");
                                boolean isAware  = false;
                                if (awareAttr instanceof Boolean) {
                                    isAware = (Boolean) awareAttr;
                                } else if (awareAttr instanceof String) {
                                    isAware = Boolean.parseBoolean((String) awareAttr);
                                }

                                double optimalStart = SmartChargingTouHelper.computeOptimalStartTime(
                                        arrivalTime, departureTime, chargingDuration,
                                        urbanEvCfg, selectedCharger, ev, isAware);

                                if (log.isDebugEnabled()) {
                                    log.debug(String.format(
                                            "SmartCharging: person=%s aware=%s homeAct=true arr=%.0f dep=%.0f dur≈%.0fs - optimalStart=%.0f",
                                            personId, isAware, arrivalTime, departureTime, chargingDuration, optimalStart));
                                }

                                if (optimalStart > arrivalTime + 1.0) {
                                    // deferred plug-in — power stored in onSmartChargePlugged callback
                                    smartScheduler.schedule(evId, selectedCharger.getId(), optimalStart);
                                    walkingDistance = DistanceUtils.calculateDistance(activityCoord, selectedCharger.getCoord());
                                    log.info(String.format(
                                            "Smart home charging: EV %s defers from t=%.0f to t=%.0f (window %.0f–%.0f, dur≈%.0fs)",
                                            ev.getId(), arrivalTime, optimalStart, arrivalTime, departureTime, chargingDuration));
                                } else {
                                    // optimum is now — immediate
                                    selectedCharger.getLogic().addVehicle(ev, arrivalTime);
                                    vehiclesAtChargers.put(evId, selectedCharger.getId());
                                    walkingDistance = DistanceUtils.calculateDistance(activityCoord, selectedCharger.getCoord());
                                    chargerPlugPowerKW.put(evId, selectedCharger.getPlugPower() / 1000.0);
                                    double socFraction = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
                                    chargeStartSoc.put(evId, socFraction);
                                    chargeStartTime.put(evId, arrivalTime);
                                }
                            } else {
                                // no window — fallback immediate
                                double t = event.getTime();
                                selectedCharger.getLogic().addVehicle(ev, t);
                                vehiclesAtChargers.put(evId, selectedCharger.getId());
                                walkingDistance = DistanceUtils.calculateDistance(activityCoord, selectedCharger.getCoord());
                                chargerPlugPowerKW.put(evId, selectedCharger.getPlugPower() / 1000.0);
                                double socFraction = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
                                chargeStartSoc.put(evId, socFraction);
                                chargeStartTime.put(evId, t);
                            }
                        } else {
                            // non-home charging or smart disabled: immediate
                            double t = event.getTime();
                            selectedCharger.getLogic().addVehicle(ev, t);
                            vehiclesAtChargers.put(evId, selectedCharger.getId());
                            walkingDistance = DistanceUtils.calculateDistance(activityCoord, selectedCharger.getCoord());
                            chargerPlugPowerKW.put(evId, selectedCharger.getPlugPower() / 1000.0);
                            double socFraction = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
                            chargeStartSoc.put(evId, socFraction);
                            chargeStartTime.put(evId, t);
                        }

                    } else {
                        // No free charger found — check if any compatible charger is simply full
                        if (isAnyCompatibleChargerFullInRadius(activityCoord, ev)) {
                            // Record estimated queue wait: all nearby chargers occupied
                            queueWaitTime.put(evId, ESTIMATED_QUEUE_WAIT_SEC);
                        }
                        // Mark charging activity as failed in plan
                        if (activity != null) {
                            actType = activity.getType() + " failed";
                            activity.setType(actType);
                        }
                    }
                }

                double time    = event.getTime();
                double soc     = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
                double startSoc = ev.getBattery().getStartSoc() / ev.getBattery().getCapacity();
                eventsManager.processEvent(new ChargingBehaviourScoringEvent(
                        time, personId, soc, walkingDistance, actType, startSoc));
            }
        }
    }

    // -------------------------------------------------------------------------
    // ActivityEndEvent — charging activity ends, fire cost-only scoring event
    // -------------------------------------------------------------------------

    @Override
    public void handleEvent(ActivityEndEvent event) {
        if (event.getActType().endsWith(CHARGING_IDENTIFIER)) {
            Id<Vehicle> vehicleId = lastVehicleUsed.get(event.getPersonId());
            if (vehicleId != null) {
                Id<ElectricVehicle> evId = Id.create(vehicleId, ElectricVehicle.class);

                // Cancel any deferred smart-charging schedule
                if (smartScheduler != null) {
                    smartScheduler.cancelIfScheduled(evId);
                }

                ElectricVehicle ev = electricFleet.getElectricVehicles().get(evId);

                // Compute energy charged and emit cost-only scoring event: OmkarP.(2025)
                if (ev != null) {
                    Double startSocFrac = chargeStartSoc.remove(evId);
                    Double startTime    = chargeStartTime.remove(evId);
                    Double plugPowerKw  = chargerPlugPowerKW.remove(evId);
                    Double waitSec      = queueWaitTime.remove(evId);

                    double energyChargedKWh = 0.0;
                    if (startSocFrac != null) {
                        double currentSocFrac = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
                        double deltaSocFrac   = currentSocFrac - startSocFrac;
                        if (deltaSocFrac > 0.0) {
                            double capacityKWh = ev.getBattery().getCapacity() / 3_600_000.0;
                            energyChargedKWh = deltaSocFrac * capacityKWh;
                        }
                    }

                    // Fall back to infrastructure lookup for power if map entry is absent
                    // (e.g. deferred smart-charging session plugged before this method ran)
                    if (plugPowerKw == null) {
                        Id<Charger> cid = vehiclesAtChargers.get(evId);
                        if (cid != null) {
                            Charger c = chargingInfrastructure.getChargers().get(cid);
                            if (c != null) plugPowerKw = c.getPlugPower() / 1000.0;
                        }
                    }

                    if (energyChargedKWh > 0.0) {
                        double pricingTime = (startTime != null) ? startTime : event.getTime();

                        String actType = event.getActType();
                        String chargerType;
                        if (actType.startsWith("home"))      { chargerType = "home"; }
                        else if (actType.startsWith("work")) { chargerType = "work"; }
                        else                                 { chargerType = "public"; }

                        if (startTime != null) {
                            double durH  = Math.max(1e-6, (event.getTime() - startTime) / 3600.0);
                            double avgKW = energyChargedKWh / durH;
                            if ("home".equals(chargerType)) {
                                log.info(String.format(
                                        "HOME session: person=%s ev=%s start=%.0f end=%.0f kWh=%.2f avg_kW=%.2f",
                                        event.getPersonId(), evId, startTime, event.getTime(), energyChargedKWh, avgKW));
                            }
                        }

                        double socFrac         = ev.getBattery().getSoc() / ev.getBattery().getCapacity();
                        double startSocForScore = ev.getBattery().getStartSoc() / ev.getBattery().getCapacity();

                        eventsManager.processEvent(new ChargingBehaviourScoringEvent(
                                event.getTime(),
                                event.getPersonId(),
                                socFrac,
                                0.0,                    // no walking component in end event
                                actType,
                                startSocForScore,
                                pricingTime,
                                energyChargedKWh,
                                chargerType,
                                true,                   // costOnly
                                plugPowerKw,            // kW for power-tier pricing
                                null,                   // detourSeconds (from InsertEnRouteCharging)
                                waitSec                 // queueWaitSeconds
                        ));
                    }
                }

                // Remove EV from charger
                Id<Charger> chargerId = vehiclesAtChargers.remove(evId);
                if (chargerId != null) {
                    Charger charger = chargingInfrastructure.getChargers().get(chargerId);
                    charger.getLogic().removeVehicle(electricFleet.getElectricVehicles().get(evId), event.getTime());
                }
            }
        }
    }

    // -------------------------------------------------------------------------
    // Other event handlers
    // -------------------------------------------------------------------------

    @Override
    public void handleEvent(PersonLeavesVehicleEvent event) {
        lastVehicleUsed.put(event.getPersonId(), event.getVehicleId());
    }

    @Override
    public void handleEvent(ChargingEndEvent event) {
        // Charging may finish before the activity ends — handled at ActivityEndEvent.
    }

    // -------------------------------------------------------------------------
    // SmartChargingEngine tick
    // -------------------------------------------------------------------------

    public void tick(double now) {
        if (smartScheduler != null) {
            smartScheduler.processDueTasks(now);
        }
    }

    // -------------------------------------------------------------------------
    // Reset
    // -------------------------------------------------------------------------

    @Override
    public void reset(int iteration) {
        lastVehicleUsed.clear();
        vehiclesAtChargers.clear();
        chargeStartSoc.clear();
        chargeStartTime.clear();
        chargerPlugPowerKW.clear();
        queueWaitTime.clear();

        if (smartScheduler != null) {
            log.info(smartScheduler.consumeStatsLine(iteration));
            smartScheduler.reset();
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Finds the best available (free) charger within parkingSearchRadius for the given EV.
     * Returns null if no compatible free charger is found.
     */
    private Charger findBestCharger(Coord stopCoord, ElectricVehicle electricVehicle) {
        List<Charger> filteredChargers = new ArrayList<>();
        chargingInfrastructure.getChargers().values().forEach(charger -> {
            if (charger.getAllowedVehicles().isEmpty()
                    || charger.getAllowedVehicles().contains(electricVehicle.getId())) {
                if (DistanceUtils.calculateDistance(stopCoord, charger.getCoord()) < parkingSearchRadius) {
                    if (electricVehicle.getChargerTypes().contains(charger.getChargerType())) {
                        if (charger.getLogic().getPluggedVehicles().size() < charger.getPlugCount()) {
                            filteredChargers.add(charger);
                        }
                    }
                }
            }
        });

        List<Charger> nearest = PartialSort.kSmallestElements(1, filteredChargers.stream(),
                charger -> DistanceUtils.calculateSquaredDistance(stopCoord, charger.getCoord()));

        if (!nearest.isEmpty()) return nearest.get(0);

        log.error("No charger found for EV " + electricVehicle.getId() + " at " + stopCoord);
        return null;
    }

    /**
     * Returns true when there is at least one compatible charger within parkingSearchRadius
     * for this EV, but ALL such chargers are currently at full capacity (no free plug).
     * Used to distinguish a genuine queue situation from a no-charger-nearby situation.
     */
    private boolean isAnyCompatibleChargerFullInRadius(Coord stopCoord, ElectricVehicle ev) {
        for (Charger charger : chargingInfrastructure.getChargers().values()) {
            if (charger.getAllowedVehicles().isEmpty()
                    || charger.getAllowedVehicles().contains(ev.getId())) {
                if (DistanceUtils.calculateDistance(stopCoord, charger.getCoord()) < parkingSearchRadius
                        && ev.getChargerTypes().contains(charger.getChargerType())) {
                    // Compatible charger in range exists — check if it's full
                    if (charger.getLogic().getPluggedVehicles().size() >= charger.getPlugCount()) {
                        return true; // at least one full compatible charger found
                    }
                }
            }
        }
        return false;
    }

    /**
     * Returns the Activity that is current or next for the given person at the given time.
     */
    private Activity getActivity(Person person, double time) {
        List<PlanElement> planElements = person.getSelectedPlan().getPlanElements();
        for (int i = 0; i < planElements.size(); i++) {
            PlanElement pe = planElements.get(i);
            if (pe instanceof Activity) {
                Activity act = (Activity) pe;
                if (act.getEndTime().isDefined()) {
                    if (act.getEndTime().seconds() > time || i == planElements.size() - 1) {
                        return act;
                    }
                } else if (i == planElements.size() - 1) {
                    return act; // last activity with no end time
                }
                // non-last activity with no end time → keep scanning
            }
        }
        return null;
    }
}
