package se.urbanEV.planning;

import se.urbanEV.scoring.ChargingBehaviourScoringEvent;
import se.urbanEV.scoring.ChargingBehaviourScoringEventHandler;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.Population;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Singleton event handler that listens for {@link ChargingBehaviourScoringEvent}s and
 * records agents whose SoC dropped below their range-anxiety threshold (or hit zero)
 * during the previous iteration.
 *
 * <p>This data is consumed by {@link InsertEnRouteChargingModule} to bias the next
 * iteration's replanning toward agents who actually had SoC problems, and by
 * {@link InsertEnRouteCharging} to prioritise trip legs where range anxiety occurred.
 *
 * <p><strong>Lifecycle:</strong>
 * <ol>
 *   <li>Call {@link #initialize(Population)} once at simulation startup (e.g. from
 *       {@code GotEVMain} or {@code MobsimScopeEventHandling.notifyStartup()}) so the
 *       collector can look up per-person {@code rangeAnxietyThreshold} attributes.</li>
 *   <li>Register the singleton with the {@code EventsManager} so it receives events.</li>
 *   <li>Call {@link #reset(int)} at the start of each iteration to clear stale records.</li>
 * </ol>
 *
 * <p>Thread safety: all mutable state uses {@link ConcurrentHashMap} / {@link
 * java.util.concurrent.CopyOnWriteArrayList} because MATSim may process events in
 * parallel.
 */
public class SocProblemCollector implements ChargingBehaviourScoringEventHandler {

    // ── Singleton ─────────────────────────────────────────────────────────────

    private static final SocProblemCollector INSTANCE = new SocProblemCollector();

    public static SocProblemCollector getInstance() {
        return INSTANCE;
    }

    /** Fallback threshold used when a person has no {@code rangeAnxietyThreshold} attribute. */
    private static final double DEFAULT_RANGE_ANXIETY_THRESHOLD = 0.2;

    // ── State ─────────────────────────────────────────────────────────────────

    /** population reference — set once via initialize(); null until then. */
    private volatile Population population;

    /**
     * personId → list of SoC problem records accumulated in the current iteration.
     * ConcurrentHashMap for thread-safe put/get; lists are only appended so
     * concurrent iteration is safe for readers who don't modify the list.
     */
    private final ConcurrentHashMap<Id<Person>, List<SocProblemRecord>> problems =
            new ConcurrentHashMap<>();

    private SocProblemCollector() {}

    // ── Initialisation ────────────────────────────────────────────────────────

    /**
     * Provides the population so this collector can read per-person
     * {@code rangeAnxietyThreshold} attributes.  Call once before the first iteration.
     */
    public static void initialize(Population population) {
        INSTANCE.population = population;
    }

    // ── ChargingBehaviourScoringEventHandler ──────────────────────────────────

    @Override
    public void handleEvent(ChargingBehaviourScoringEvent event) {
        // Cost-only events carry monetary data, not SoC state — skip them.
        if (event.isCostOnly()) return;

        Double socObj = event.getSoc();
        if (socObj == null) return;

        double soc         = socObj;
        Id<Person> pid     = event.getPersonId();
        double threshold   = resolveThreshold(pid);

        // Record a problem if the agent's SoC is at or below their threshold
        if (soc <= 0.0 || soc < threshold) {
            SocProblemRecord record = new SocProblemRecord(
                    pid,
                    event.getTime(),
                    soc,
                    event.getActivityType()
            );
            problems
                .computeIfAbsent(pid, k -> Collections.synchronizedList(new ArrayList<>()))
                .add(record);
        }
    }

    @Override
    public void reset(int iteration) {
        problems.clear();
    }

    // ── Query API ─────────────────────────────────────────────────────────────

    /**
     * Returns true if the given person had at least one SoC-below-threshold event in
     * the most recently completed iteration.
     */
    public boolean hadProblems(Id<Person> personId) {
        List<SocProblemRecord> list = problems.get(personId);
        return list != null && !list.isEmpty();
    }

    /**
     * Returns all SoC problem records for the given person from the most recently
     * completed iteration.  Returns an empty list if none were recorded.
     */
    public List<SocProblemRecord> getProblemsForPerson(Id<Person> personId) {
        List<SocProblemRecord> list = problems.get(personId);
        if (list == null) return Collections.emptyList();
        return Collections.unmodifiableList(list);
    }

    /** Returns the total number of persons who had at least one SoC problem. */
    public int getProblemPersonCount() {
        return problems.size();
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private double resolveThreshold(Id<Person> personId) {
        if (population == null) return DEFAULT_RANGE_ANXIETY_THRESHOLD;
        Person person = population.getPersons().get(personId);
        if (person == null) return DEFAULT_RANGE_ANXIETY_THRESHOLD;
        Object attr = person.getAttributes().getAttribute("rangeAnxietyThreshold");
        if (attr != null) {
            try { return Double.parseDouble(attr.toString()); }
            catch (NumberFormatException ignored) { }
        }
        return DEFAULT_RANGE_ANXIETY_THRESHOLD;
    }

    // ── SocProblemRecord ──────────────────────────────────────────────────────

    /**
     * Immutable record of a single SoC-below-threshold event for one person.
     */
    public static final class SocProblemRecord {

        /** The person who experienced the SoC problem. */
        public final Id<Person> personId;

        /** Simulation time (seconds) at which the problem was detected. */
        public final double time;

        /** State of charge (0–1 fraction of capacity) at the moment of detection. */
        public final double soc;

        /** Activity type string from the scoring event (e.g. "other", "work charging"). */
        public final String activityType;

        public SocProblemRecord(Id<Person> personId, double time, double soc, String activityType) {
            this.personId     = personId;
            this.time         = time;
            this.soc          = soc;
            this.activityType = activityType;
        }

        @Override
        public String toString() {
            return String.format("SocProblem[person=%s t=%.0f soc=%.3f act=%s]",
                    personId, time, soc, activityType);
        }
    }
}
