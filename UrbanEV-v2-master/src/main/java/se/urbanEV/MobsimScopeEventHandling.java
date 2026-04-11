/*
File originally created, published and licensed by contributors of the org.matsim.* project.
Please consider the original license notice below.
This is a modified version of the original source code!

Modified 2020 by Lennart Adenaw, Technical University Munich, Chair of Automotive Technology
email	:	lennart.adenaw@tum.de
*/

/* ORIGINAL LICENSE
 * *********************************************************************** *
 * project: org.matsim.*
 * *********************************************************************** *
 *                                                                         *
 * copyright       : (C) 2019 by the members listed in the COPYING,        *
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
 * *********************************************************************** *
 */

package se.urbanEV;

import org.apache.log4j.Logger;
import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.fleet.*;
import se.urbanEV.infrastructure.*;
import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.population.Activity;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.PlanElement;
import org.matsim.api.core.v01.population.Population;
import org.matsim.contrib.ev.EvUnits;
import org.matsim.contrib.ev.MobsimScopeEventHandler;
import org.matsim.contrib.util.CSVReaders;
import org.matsim.core.api.experimental.events.EventsManager;
import org.matsim.core.config.Config;
import org.matsim.core.controler.IterationCounter;
import org.matsim.core.controler.MatsimServices;
import org.matsim.core.controler.OutputDirectoryHierarchy;
import org.matsim.core.controler.events.AfterMobsimEvent;
import org.matsim.core.controler.events.StartupEvent;
import org.matsim.core.controler.listener.AfterMobsimListener;
import org.matsim.core.controler.listener.StartupListener;
import org.matsim.core.replanning.StrategyManager;
import org.matsim.core.utils.misc.Time;

import javax.inject.Inject;
import javax.inject.Singleton;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Meant for event handlers that are created anew in each iteration and should operate only until the end of the current
 * mobsim. Typically, these are event handlers created in AbstractQSimModules.
 *
 * @author Michal Maciejewski (michalm)
 */
@Singleton
public class MobsimScopeEventHandling implements StartupListener, AfterMobsimListener {
	private static final Logger log = Logger.getLogger(MobsimScopeEventHandling.class);
	private final Collection<MobsimScopeEventHandler> eventHandlers = new ConcurrentLinkedQueue<>();
	private final EventsManager eventsManager;
	private Random random = new Random();
	private StrategyManager strategyManager;

	private int iterationNumber = 0;
	private int lastIteration = 0;
	private double endTime = 0;

	@Inject
	public MobsimScopeEventHandling(EventsManager eventsManager) {
		this.eventsManager = eventsManager;
	}

	@Inject
	private ChargingInfrastructureSpecification chargingInfrastructureSpecification;

	@Inject
	private Population population;

	@Inject
	private ElectricFleetSpecification electricFleetSpecification;

	@Inject
	private OutputDirectoryHierarchy controlerIO;

	@Inject
	private IterationCounter iterationCounter;

	@Inject
	private MatsimServices matsimServices;

	@Inject
	private Config config;

	@Inject
	private UrbanEVConfigGroup urbanEVConfig;

	// Workplace charger clustering (Wood et al. 2018, NREL)
	private final java.util.Map<String, WorkplaceCluster> workplaceClusters = new java.util.HashMap<>();

	private static class WorkplaceCluster {
		final Coord coord;
		final double power;
		int workerCount = 0;
		WorkplaceCluster(Coord coord, double power) {
			this.coord = coord;
			this.power = power;
		}
	}

	public void addMobsimScopeHandler(MobsimScopeEventHandler handler) {
		eventHandlers.add(handler);
		eventsManager.addHandler(handler);
	}


	@Override
	public void notifyStartup(StartupEvent startupEvent) {
		lastIteration = config.controler().getLastIteration();
		endTime = config.qsim().getEndTime().seconds();
		strategyManager = matsimServices.getStrategyManager();

        population.getPersons().forEach((personId, person) -> {

			// add default range anxiety threshold to person attributes if none given
			if (person.getAttributes().getAttribute("rangeAnxietyThreshold") == null) {
				person.getAttributes().putAttribute("rangeAnxietyThreshold", String.valueOf(urbanEVConfig.getDefaultRangeAnxietyThreshold()));
			}

			// add work and home chargers
			// Todo: Generalize this for any kind of private charging infrastructure

			double homeChargerPower;
			double workChargerPower;

			// Determine home charging power
			if(!urbanEVConfig.isGenerateHomeChargersByPercentage()) {
				// Generate home chargers based on population attributes
				homeChargerPower = person.getAttributes().getAttribute("homeChargerPower") != null ? Double.parseDouble(person.getAttributes().getAttribute("homeChargerPower").toString()) : 0.0;
			} else {
				if(random.nextDouble()<=urbanEVConfig.getHomeChargerPercentage()/100.0){
					// Randomly assign home charger with the corresponding probability
					homeChargerPower = urbanEVConfig.getDefaultHomeChargerPower();
				} else {
					homeChargerPower = 0.0;
				}
			}

			// Determine work charging power
			if(!urbanEVConfig.isGenerateWorkChargersByPercentage()) {
				// Generate work chargers based on population attributes
				workChargerPower = person.getAttributes().getAttribute("workChargerPower") != null ? Double.parseDouble(person.getAttributes().getAttribute("workChargerPower").toString()) : 0.0;
			} else {
				if(random.nextDouble()<=urbanEVConfig.getWorkChargerPercentage()/100.0){
					// Randomly assign work charger with the corresponding probability
					workChargerPower = urbanEVConfig.getDefaultWorkChargerPower();
				} else {
					workChargerPower = 0.0;
				}
			}

			// Add home charger (always private, per-agent)
			if(homeChargerPower!=0.0) addPrivateCharger(person, "home", homeChargerPower);

			// Collect work charger demand for shared workplace pools
			// (Wood et al. 2018, NREL: shared chargers with 1:5 ratio)
			if(workChargerPower!=0.0) {
				Coord foundWorkCoord = null;
				for (PlanElement pe : person.getSelectedPlan().getPlanElements()) {
					if (pe instanceof Activity && ((Activity) pe).getType().startsWith("work")) {
						foundWorkCoord = ((Activity) pe).getCoord();
						break;
					}
				}
				if (foundWorkCoord != null) {
					final Coord wc = foundWorkCoord;
					final double wcp = workChargerPower;
					double clusterR = urbanEVConfig.getWorkplaceClusterRadius();
					String clusterKey = (long)(wc.getX()/clusterR)*((long)clusterR)
							+ "_" + (long)(wc.getY()/clusterR)*((long)clusterR);
					workplaceClusters.computeIfAbsent(clusterKey, k -> new WorkplaceCluster(wc, wcp));
					workplaceClusters.get(clusterKey).workerCount++;
				}
			}

        });

		// Phase 2: Create shared workplace charger pools (Dong & Lin 2023)
		int ratio = urbanEVConfig.getWorkplaceChargerRatio();
		int wpChargers = 0;
		for (java.util.Map.Entry<String, WorkplaceCluster> entry : workplaceClusters.entrySet()) {
			WorkplaceCluster cluster = entry.getValue();
			int plugCount = Math.max(1, cluster.workerCount / ratio);
			String chargerId = "workplace_" + entry.getKey();
			String chargerType = (cluster.power >= urbanEVConfig.getL2PowerThreshold()) ? "L2" : "L1";

			ChargerSpecification spec = ImmutableChargerSpecification.newBuilder()
					.id(Id.create(chargerId, Charger.class))
					.coord(new Coord(cluster.coord.getX(), cluster.coord.getY()))
					.chargerType(chargerType)
					.plugPower(EvUnits.kW_to_W(cluster.power))
					.plugCount(plugCount)
					.allowedVehicles(new java.util.ArrayList<>())  // empty = open to all
					.build();
			chargingInfrastructureSpecification.addChargerSpecification(spec);
			wpChargers++;
		}
		log.info("Workplace charging: created " + wpChargers + " shared charger pools "
				+ "(ratio 1:" + ratio + ") from " + workplaceClusters.values().stream()
				.mapToInt(c -> c.workerCount).sum() + " EV workers");

        // Write final chargers to file
		ChargerWriter chargerWriter = new ChargerWriter(chargingInfrastructureSpecification.getChargerSpecifications().values().stream());
		chargerWriter.write(config.controler().getOutputDirectory().concat("/chargers_complete.xml"));
	}

	/**
	 * After each mobsim: carry forward per-vehicle SoC to the next iteration.
	 *
	 * <p>Replaces the original soc_histogram-based approach (which crashed when
	 * the histogram file was not generated) with direct per-vehicle SoC carry-forward
	 * as described in Baum et al. (2022). Each vehicle's end-of-day SoC becomes
	 * its initial SoC for the next iteration, enabling multi-day learning dynamics.
	 *
	 * <p>This is critical for agents without home chargers: their SoC gradually
	 * depletes across iterations, forcing them to seek public charging.
	 */
	@Override
	public void notifyAfterMobsim(AfterMobsimEvent event) {
		iterationNumber = iterationCounter.getIterationNumber();

		// Capture end-of-day SoC before handlers are removed
		for (MobsimScopeEventHandler handler : eventHandlers) {
			if (handler instanceof se.urbanEV.discharging.DriveDischargingHandler) {
				((se.urbanEV.discharging.DriveDischargingHandler) handler).captureEndOfDaySoc();
			}
		}

		eventHandlers.forEach(eventsManager::removeHandler);
		eventHandlers.clear();

		if (!urbanEVConfig.isEnableSocPersistence()) return;

		// ── Simple SoC carry-forward (no overnight model) ──────────────────────
		// With multi-day plans, overnight charging happens IN the simulation
		// via "home charging" activities. No external manipulation needed.
		// Just carry the end-of-simulation SoC to the next iteration's start.
		// The co-evolutionary scoring function teaches agents to charge at home.

		java.util.Map<Id<ElectricVehicle>, Double> finalSocMap =
				se.urbanEV.discharging.DriveDischargingHandler.getLastIterationFinalSoc();

		if (finalSocMap.isEmpty()) {
			log.info("SoC persistence: no final SoC data (iteration " + iterationNumber + ")");
			return;
		}

		int updated = 0;
		for (java.util.Map.Entry<Id<ElectricVehicle>, ElectricVehicleSpecification> entry
				: electricFleetSpecification.getVehicleSpecifications().entrySet()) {
			Id<ElectricVehicle> evId = entry.getKey();
			ElectricVehicleSpecification oldSpec = entry.getValue();
			Double finalSoc = finalSocMap.get(evId);

			if (finalSoc == null) continue;

			double clampedSoc = Math.max(0, Math.min(finalSoc, oldSpec.getBatteryCapacity()));
			ElectricVehicleSpecification newSpec = ImmutableElectricVehicleSpecification.newBuilder()
					.id(evId)
					.vehicleType(oldSpec.getVehicleType())
					.chargerTypes(oldSpec.getChargerTypes())
					.initialSoc(clampedSoc)
					.batteryCapacity(oldSpec.getBatteryCapacity())
					.build();
			electricFleetSpecification.replaceVehicleSpecification(newSpec);
			updated++;
		}

		log.info(String.format(
				"SoC persistence (iter %d): %d vehicles — simple carry-forward, no overnight model",
				iterationNumber, updated));

		// Write fleet state at final iteration for external analysis
		if (iterationNumber == lastIteration) {
			try {
				ElectricFleetWriter writer = new ElectricFleetWriter(
						electricFleetSpecification.getVehicleSpecifications().values().stream());
				writer.write(Paths.get(controlerIO.getOutputPath(), "output_evehicles.xml").toString());
			} catch (Exception e) {
				log.warn("Could not write final EV fleet state: " + e.getMessage());
			}
		}
	}


	private void addPrivateCharger(Person person, String activityType, double power) {
		String ownerId = person.getId().toString();
		String chargerId = ownerId + "_" + activityType;
		Coord actCoord = new Coord();
		for (PlanElement planElement : person.getSelectedPlan().getPlanElements()) {
			if (planElement instanceof Activity) {
				Activity act = (Activity) planElement;
				if (act.getType().startsWith(activityType)) {
					actCoord = act.getCoord();
					break;
				}
			}
		}
		// Derive charger type from plug power so it matches vehicle charger_types (L1/L2).
		// Private chargers are never DCFC; threshold follows the config group.
		String chargerType = (power >= urbanEVConfig.getL2PowerThreshold()) ? "L2" : "L1";
		int plugCount = ChargerSpecification.DEFAULT_PLUG_COUNT;
		List<Id<ElectricVehicle>> allowedEvIds = new ArrayList();
		allowedEvIds.add(Id.create(ownerId, ElectricVehicle.class));

		ChargerSpecification chargerSpecification = ImmutableChargerSpecification.newBuilder()
				.id(Id.create(chargerId, Charger.class))
				.coord(new Coord(actCoord.getX(), actCoord.getY()))
				.chargerType(chargerType)
				.plugPower(EvUnits.kW_to_W(power))
				.plugCount(plugCount)
				.allowedVehicles(allowedEvIds)
				.build();

		chargingInfrastructureSpecification.addChargerSpecification(chargerSpecification);
	}
}
