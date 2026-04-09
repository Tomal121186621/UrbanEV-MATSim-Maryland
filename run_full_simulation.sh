#!/usr/bin/env bash
# ============================================================================
# run_full_simulation.sh
# Runs the full Maryland+DC UrbanEV simulation.
# Auto-detects available RAM and CPU cores. Works on 64 GB+ systems.
#
# Usage:
#   cd "UrbanEV-MATSim-Maryland-main"
#   bash run_full_simulation.sh [--skip-build]
#
# Output:
#   scenarios/maryland/output/maryland_ev_enhanced/
#   Log: full_simulation.log
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/UrbanEV-v2-master"
CONFIG_FILE="scenarios/maryland/config.xml"
JAR_FILE="$PROJECT_ROOT/target/urban_ev-0.1-jar-with-dependencies.jar"
LOG_FILE="$SCRIPT_DIR/full_simulation.log"

# Add Maven to PATH if installed at standard location
if [ -d "/c/tools/apache-maven-3.9.9/bin" ]; then
    export PATH="/c/tools/apache-maven-3.9.9/bin:$PATH"
fi

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

# ── Auto-detect system resources ─────────────────────────────────────────────
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
NUM_CORES=$(nproc 2>/dev/null || echo 4)

# Reserve ~25% for OS + overhead, use 75% for JVM
JVM_MAX_GB=$((TOTAL_RAM_GB * 75 / 100))
if [ "$JVM_MAX_GB" -lt 48 ]; then
    fail "Insufficient RAM: ${TOTAL_RAM_GB}GB detected, need at least 64GB. The 9.8M link network requires ~50GB."
fi
if [ "$JVM_MAX_GB" -gt 120 ]; then
    JVM_MAX_GB=120  # cap — no need for more
fi

# QSim threads: cores - 2 (leave room for OS and GC)
QSIM_THREADS=$((NUM_CORES - 2))
if [ "$QSIM_THREADS" -lt 2 ]; then QSIM_THREADS=2; fi
if [ "$QSIM_THREADS" -gt 14 ]; then QSIM_THREADS=14; fi

# GC threads: ~cores
GC_THREADS=$((NUM_CORES))
if [ "$GC_THREADS" -gt 14 ]; then GC_THREADS=14; fi

info "System: ${TOTAL_RAM_GB}GB RAM, ${NUM_CORES} cores"
info "JVM:    -Xmx${JVM_MAX_GB}g, ${QSIM_THREADS} QSim threads, ${GC_THREADS} GC threads"

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
info "Step 2: Launching simulation (130K agents, 30 iterations)..."
info "Log: $LOG_FILE"
info "Config: $CONFIG_FILE"
echo ""

cd "$SCRIPT_DIR"

java \
    -Xmx${JVM_MAX_GB}g \
    -Xms8g \
    -XX:+UseG1GC \
    -XX:G1HeapRegionSize=32m \
    -XX:ParallelGCThreads=${GC_THREADS} \
    -XX:ConcGCThreads=4 \
    -XX:+UseStringDeduplication \
    --add-opens java.base/java.lang=ALL-UNNAMED \
    --add-opens java.base/java.util=ALL-UNNAMED \
    --add-opens java.base/java.lang.invoke=ALL-UNNAMED \
    -cp "$JAR_FILE" \
    se.got.GotEVMain \
    "$CONFIG_FILE" \
    0 \
    2>&1 | tee "$LOG_FILE" | grep -E "(INFO|WARN|ERROR|Exception|Iteration|it\.|score|SIM_STEP|Mobsim|Replanning|SocProblem|InsertEnRoute|SoC persistence|Workplace|ChargerReliability|HOME session)" | grep -v "^$"

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
