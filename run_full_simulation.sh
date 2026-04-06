#!/usr/bin/env bash
# ============================================================================
# run_full_simulation.sh
# Runs the full Maryland+DC EV simulation (116K agents, 60 iterations).
# Tuned for AMD Ryzen 7 2700X (8 cores / 16 threads), 128 GB RAM.
#
# Usage:
#   cd "UrbanEV-MATSim-Maryland-main"
#   bash run_full_simulation.sh [--skip-build]
#
# Output:
#   scenarios/maryland/output/maryland_ev_enhanced/
#   Log: full_simulation.log (tailed to console, full log to file)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/UrbanEV-v2-master"
CONFIG_FILE="scenarios/maryland/config.xml"
JAR_FILE="$PROJECT_ROOT/target/urban_ev-0.1-jar-with-dependencies.jar"
LOG_FILE="$SCRIPT_DIR/full_simulation.log"

# Add Maven to PATH if installed at standard location
export PATH="/c/tools/apache-maven-3.9.9/bin:$PATH"

SKIP_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: bash run_full_simulation.sh [--skip-build]"
            exit 1
            ;;
    esac
done

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

# ── Step 1: Maven build ───────────────────────────────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    info "Step 1: Building UrbanEV-v2 JAR (Maven)..."
    cd "$PROJECT_ROOT"
    mvn -q clean package -DskipTests -Denforcer.skip=true 2>&1 | tail -20
    BUILD_EXIT=$?
    cd "$SCRIPT_DIR"
    [ $BUILD_EXIT -eq 0 ] || fail "Maven build failed (exit $BUILD_EXIT)"
    ok "Maven build succeeded"
else
    info "Step 1: Skipping Maven build (--skip-build)"
fi

[ -f "$JAR_FILE" ] || fail "JAR not found: $JAR_FILE"
info "Using JAR: $JAR_FILE"

# ── Step 2: Run simulation ────────────────────────────────────────────────────
info "Step 2: Launching full Maryland+DC simulation (116K agents, 60 iterations)..."
info "Log → $LOG_FILE"
info "Config: $CONFIG_FILE"
echo ""

cd "$SCRIPT_DIR"

# JVM tuning for AMD Ryzen 7 2700X (8 cores / 16 threads, 128 GB RAM):
#   -Xmx64g          — 64 GB heap; plenty of headroom with 128 GB total
#   -Xms16g          — pre-allocate 16 GB to avoid early GC pressure
#   -XX:+UseG1GC     — G1 GC: best latency/throughput balance for large heaps
#   -XX:G1HeapRegionSize=32m  — 32 MB regions suits large heap
#   -XX:ParallelGCThreads=12  — GC uses 12 threads
#   -XX:ConcGCThreads=4       — concurrent GC marking threads
#   -XX:+UseStringDeduplication — reduces repeated String objects in plans/events
#   --add-opens       — required for Guice CGLIB proxy generation on JDK 17+

java \
    -Xmx64g \
    -Xms16g \
    -XX:+UseG1GC \
    -XX:G1HeapRegionSize=32m \
    -XX:ParallelGCThreads=12 \
    -XX:ConcGCThreads=4 \
    -XX:+UseStringDeduplication \
    --add-opens java.base/java.lang=ALL-UNNAMED \
    --add-opens java.base/java.util=ALL-UNNAMED \
    --add-opens java.base/java.lang.invoke=ALL-UNNAMED \
    -cp "$JAR_FILE" \
    se.got.GotEVMain \
    "$CONFIG_FILE" \
    0 \
    2>&1 | tee "$LOG_FILE" | grep -E "(INFO|WARN|ERROR|Exception|Iteration|it\.|score|SIM_STEP|Mobsim|Replanning)" | grep -v "^$"

SIM_EXIT=${PIPESTATUS[0]}

echo ""
if [ $SIM_EXIT -eq 0 ]; then
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  SIMULATION COMPLETE                                     ${NC}"
    echo -e "${GREEN}  Output: scenarios/maryland/output/maryland_ev_enhanced/ ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
else
    echo -e "${RED}══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  SIMULATION FAILED (exit $SIM_EXIT) — see full_simulation.log  ${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════════${NC}"
    exit $SIM_EXIT
fi
