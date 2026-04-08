package se.urbanEV.charging;

import org.apache.log4j.Logger;
import org.matsim.api.core.v01.Id;
import org.matsim.core.controler.events.IterationStartsEvent;
import org.matsim.core.controler.listener.IterationStartsListener;
import se.urbanEV.config.UrbanEVConfigGroup;
import se.urbanEV.infrastructure.Charger;
import se.urbanEV.infrastructure.ChargerSpecification;
import se.urbanEV.infrastructure.ChargingInfrastructureSpecification;
import se.urbanEV.infrastructure.ImmutableChargerSpecification;

import javax.inject.Inject;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * Per-iteration stochastic charger downtime simulation.
 *
 * <p>Based on NREL reliability data (Rempel et al. 2022, NREL/TP-5400-83459):
 * <ul>
 *   <li>DCFC uptime: 78–80% per-plug (national average)</li>
 *   <li>L2 uptime: 90–95% per-plug</li>
 * </ul>
 *
 * <p>Each iteration, every charger plug is independently tested against the
 * uptime probability. If all plugs fail, the charger is effectively offline.
 * This models the real-world experience where drivers arrive at chargers
 * that are broken, offline, or ICE'd (blocked by non-EV vehicles).
 *
 * <p>Agents learn to cope with unreliable chargers through MATSim's
 * evolutionary replanning — plans that rely on unreliable chargers score
 * lower and are replaced by alternatives.
 *
 * <p>The manager preserves original plug counts and restores them before
 * re-randomizing each iteration, ensuring the baseline is consistent.
 *
 * @author OmkarP (2025)
 */
public class ChargerReliabilityManager implements IterationStartsListener {
    private static final Logger log = Logger.getLogger(ChargerReliabilityManager.class);

    private final ChargingInfrastructureSpecification infraSpec;
    private final UrbanEVConfigGroup config;
    private final Map<Id<Charger>, Integer> originalPlugCounts = new HashMap<>();
    private boolean initialized = false;

    @Inject
    public ChargerReliabilityManager(ChargingInfrastructureSpecification infraSpec,
                                      UrbanEVConfigGroup config) {
        this.infraSpec = infraSpec;
        this.config = config;
    }

    @Override
    public void notifyIterationStarts(IterationStartsEvent event) {
        if (!config.isEnableChargerReliability()) return;

        Random rng = new Random(42L + event.getIteration());

        // Save original plug counts on first call
        if (!initialized) {
            for (ChargerSpecification cs : infraSpec.getChargerSpecifications().values()) {
                originalPlugCounts.put(cs.getId(), cs.getPlugCount());
            }
            initialized = true;
        }

        double dcfcUptime = config.getDcfcChargerUptime();
        double l2Uptime = config.getL2ChargerUptime();
        double dcfcThresholdW = config.getDcfcPowerThreshold() * 1000.0; // kW → W

        int totalPlugs = 0;
        int disabledPlugs = 0;
        int offlineChargers = 0;

        for (ChargerSpecification cs : infraSpec.getChargerSpecifications().values()) {
            // Skip private chargers (home chargers — always available)
            if (!cs.getAllowedVehicles().isEmpty()) continue;

            int originalPlugs = originalPlugCounts.getOrDefault(cs.getId(), cs.getPlugCount());
            double uptime = (cs.getPlugPower() > dcfcThresholdW) ? dcfcUptime : l2Uptime;

            // Per-plug independent availability check
            int availablePlugs = 0;
            for (int i = 0; i < originalPlugs; i++) {
                if (rng.nextDouble() < uptime) availablePlugs++;
            }

            totalPlugs += originalPlugs;
            disabledPlugs += (originalPlugs - availablePlugs);
            if (availablePlugs == 0) offlineChargers++;

            // Replace specification with updated plug count
            if (availablePlugs != cs.getPlugCount()) {
                ChargerSpecification updated = ImmutableChargerSpecification.newBuilder()
                        .id(cs.getId())
                        .coord(cs.getCoord())
                        .chargerType(cs.getChargerType())
                        .plugPower(cs.getPlugPower())
                        .plugCount(Math.max(0, availablePlugs))
                        .allowedVehicles(cs.getAllowedVehicles())
                        .build();
                infraSpec.replaceChargerSpecification(updated);
            }
        }

        log.info(String.format(
                "ChargerReliability: iteration %d — %d/%d plugs disabled (%.1f%%), %d chargers fully offline",
                event.getIteration(), disabledPlugs, totalPlugs,
                disabledPlugs * 100.0 / Math.max(1, totalPlugs), offlineChargers));
    }
}
