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
 * copyright       : (C) 2015 by the members listed in the COPYING,        *
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

package se.urbanEV.discharging;

import com.google.inject.Inject;
import org.apache.log4j.Logger;
import se.urbanEV.MobsimScopeEventHandling;
import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.fleet.ElectricFleet;
import se.urbanEV.fleet.ElectricVehicle;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.LinkLeaveEvent;
import org.matsim.api.core.v01.events.VehicleEntersTrafficEvent;
import org.matsim.api.core.v01.events.VehicleLeavesTrafficEvent;
import org.matsim.api.core.v01.events.handler.LinkLeaveEventHandler;
import org.matsim.api.core.v01.events.handler.VehicleEntersTrafficEventHandler;
import org.matsim.api.core.v01.events.handler.VehicleLeavesTrafficEventHandler;
import org.matsim.api.core.v01.network.Link;
import org.matsim.api.core.v01.network.Network;
import org.matsim.contrib.ev.EvConfigGroup;
import org.matsim.contrib.ev.MobsimScopeEventHandler;
import org.matsim.vehicles.Vehicle;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Because in QSim and JDEQSim vehicles enter and leave traffic at the end of links, we skip the first link when
 * calculating the drive-related energy consumption. However, the time spent on the first link is used by the time-based
 * aux discharge process (see {@link AuxDischargingHandler}).
 */
public class DriveDischargingHandler
		implements LinkLeaveEventHandler, VehicleEntersTrafficEventHandler, VehicleLeavesTrafficEventHandler,
		MobsimScopeEventHandler {
	private static final Logger log = Logger.getLogger(DriveDischargingHandler.class);

	/** Gasoline energy density: 34.2 MJ/L (lower heating value). */
	private static final double GASOLINE_ENERGY_DENSITY_J_PER_L = 34_200_000.0;

	private static class EvDrive {
		private final Id<Vehicle> vehicleId;
		private final ElectricVehicle ev;
		private double movedOverNodeTime;

		public EvDrive(Id<Vehicle> vehicleId, ElectricVehicle ev) {
			this.vehicleId = vehicleId;
			this.ev = ev;
			movedOverNodeTime = Double.NaN;
		}

		private boolean isOnFirstLink() {
			return Double.isNaN(movedOverNodeTime);
		}
	}

	private final Network network;
	private final Map<Id<ElectricVehicle>, ? extends ElectricVehicle> eVehicles;
	private final Map<Id<Vehicle>, EvDrive> evDrives;
	private Map<Id<Link>, Double> energyConsumptionPerLink = new HashMap<>();

	// ── PHEV gas fallback tracking (Axsen et al. 2020, Raghavan & Tal 2020) ──
	private final Map<Id<ElectricVehicle>, Double> gasUsageLiters = new HashMap<>();

	// ── Multi-day SoC persistence (Baum et al. 2022) ──
	// Stores final SoC (Joules) for each vehicle at end of mobsim.
	// Read by MobsimScopeEventHandling.notifyAfterMobsim() for carry-forward.
	private static final Map<Id<ElectricVehicle>, Double> lastIterationFinalSoc = new HashMap<>();

	/** Returns the final SoC map from the last completed mobsim. Thread-safe read. */
	public static Map<Id<ElectricVehicle>, Double> getLastIterationFinalSoc() {
		return Collections.unmodifiableMap(lastIterationFinalSoc);
	}

	/** Called at end of mobsim to snapshot all vehicle SoC values. */
	public void captureEndOfDaySoc() {
		lastIterationFinalSoc.clear();
		for (Map.Entry<Id<ElectricVehicle>, ? extends ElectricVehicle> entry : eVehicles.entrySet()) {
			lastIterationFinalSoc.put(entry.getKey(), entry.getValue().getBattery().getSoc());
		}
		log.info("SoC persistence: captured end-of-day SoC for " + lastIterationFinalSoc.size() + " vehicles");
	}
	private final double phevMinSocFraction;
	private final double phevCSEfficiency;
	private long phevGasSwitchCount = 0;

	@Inject
	public DriveDischargingHandler(ElectricFleet data, Network network, EvConfigGroup evCfg,
                                   MobsimScopeEventHandling events, UrbanEVConfigGroup urbanEvCfg) {
		this.network = network;
		eVehicles = data.getElectricVehicles();
		evDrives = new HashMap<>(eVehicles.size() / 10);
		this.phevMinSocFraction = (urbanEvCfg != null) ? urbanEvCfg.getPhevMinSocFraction() : 0.15;
		this.phevCSEfficiency = (urbanEvCfg != null) ? urbanEvCfg.getPhevCSEfficiency() : 0.30;
		events.addMobsimScopeHandler(this);
	}

	/**
	 * Returns true if the vehicle is a PHEV (plug-in hybrid) based on its type name.
	 * PHEVs can fall back to gasoline when battery is depleted.
	 */
	private boolean isPhev(ElectricVehicle ev) {
		String typeName = ev.getVehicleType().getId().toString().toLowerCase();
		return typeName.contains("phev") || typeName.contains("4xe") || typeName.contains("prime")
			|| typeName.contains("recharge") || typeName.contains("350e") || typeName.contains("xdrive");
	}

	/** Accumulated gasoline usage per EV (liters). Read-only view for scoring. */
	public Map<Id<ElectricVehicle>, Double> getGasUsageLiters() {
		return Collections.unmodifiableMap(gasUsageLiters);
	}

	public long getPhevGasSwitchCount() { return phevGasSwitchCount; }

	@Override
	public void handleEvent(VehicleEntersTrafficEvent event) {
		Id<Vehicle> vehicleId = event.getVehicleId();
		ElectricVehicle ev = eVehicles.get(vehicleId);
		if (ev != null) {// handle only our EVs
			evDrives.put(vehicleId, new EvDrive(vehicleId, ev));
		}
	}

	@Override
	public void handleEvent(LinkLeaveEvent event) {
		EvDrive evDrive = dischargeVehicle(event.getVehicleId(), event.getLinkId(), event.getTime());
		if (evDrive != null) {
			evDrive.movedOverNodeTime = event.getTime();
		}
	}

	@Override
	public void handleEvent(VehicleLeavesTrafficEvent event) {
		EvDrive evDrive = dischargeVehicle(event.getVehicleId(), event.getLinkId(), event.getTime());
		if (evDrive != null) {
			evDrives.remove(evDrive.vehicleId);
		}
	}

	//XXX The current implementation is thread-safe because no other EventHandler modifies battery SOC
	// (for instance, AUX discharging and battery charging modifies SOC outside event handling
	// (as MobsimAfterSimStepListeners)
	//TODO In the long term, it will be safer to move the discharging procedure to a MobsimAfterSimStepListener
	/**
	 * Discharge vehicle battery for traversing a link. For PHEVs, if the battery
	 * would drop below {@code phevMinSocFraction}, the remaining energy demand is
	 * satisfied by the gasoline engine in charge-sustaining (CS) mode.
	 *
	 * <p>Based on the CD/CS (charge-depleting / charge-sustaining) two-state model
	 * described in Axsen et al. (2020) and Raghavan & Tal (2020). The CS-mode fuel
	 * consumption is derived from the electrical energy demand and the engine's
	 * thermal efficiency: {@code gasLiters = energy_J / (LHV_gasoline * efficiency)}.
	 */
	private EvDrive dischargeVehicle(Id<Vehicle> vehicleId, Id<Link> linkId, double eventTime) {
		EvDrive evDrive = evDrives.get(vehicleId);
		if (evDrive != null && !evDrive.isOnFirstLink()) {
			Link link = network.getLinks().get(linkId);
			double tt = eventTime - evDrive.movedOverNodeTime;
			ElectricVehicle ev = evDrive.ev;
			double energy = ev.getDriveEnergyConsumption().calcEnergyConsumption(link, tt, eventTime - tt)
					+ ev.getAuxEnergyConsumption().calcEnergyConsumption(eventTime - tt, tt, linkId);

			double currentSoc = ev.getBattery().getSoc();
			double minSoc = ev.getBattery().getCapacity() * phevMinSocFraction;

			// PHEV gas fallback: CD/CS mode switching
			if (isPhev(ev) && currentSoc - energy < minSoc && energy > 0) {
				// Use remaining electric energy down to minSoc, rest from gasoline
				double electricEnergy = Math.max(0, currentSoc - minSoc);
				double gasEnergy = energy - electricEnergy;

				ev.getBattery().changeSoc(-electricEnergy);

				// Convert gasEnergy (Joules) to liters of gasoline
				// gasLiters = energy / (LHV * efficiency)
				double gasLiters = gasEnergy / (GASOLINE_ENERGY_DENSITY_J_PER_L * phevCSEfficiency);
				gasUsageLiters.merge(Id.create(vehicleId, ElectricVehicle.class), gasLiters, Double::sum);
				phevGasSwitchCount++;
			} else {
				// Normal BEV discharge (or PHEV still in CD mode)
				ev.getBattery().changeSoc(-energy);
			}

			double linkConsumption = energy + energyConsumptionPerLink.getOrDefault(linkId, 0.0);
			energyConsumptionPerLink.put(linkId, linkConsumption);
		}
		return evDrive;
	}

	public Map<Id<Link>, Double> getEnergyConsumptionPerLink() {
		return energyConsumptionPerLink;
	}
}
