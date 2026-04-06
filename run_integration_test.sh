#!/usr/bin/env bash
# ============================================================================
# run_integration_test.sh
# Builds the UrbanEV-v2 JAR and runs the 15-iteration integration test,
# then calls validate_test_output.py to check all 8 assertions.
#
# Usage:
#   cd "URBAN EV Version 2_Reframed"
#   bash run_integration_test.sh [--skip-build] [--skip-sim]
#
# Options:
#   --skip-build   Skip Maven build (use existing JAR)
#   --skip-sim     Skip simulation run (use existing output)
# ============================================================================

set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/UrbanEV-v2-master"
SCENARIO_DIR="$SCRIPT_DIR/test_scenario"
CONFIG_FILE="$SCENARIO_DIR/test_config.xml"
OUTPUT_DIR="$SCENARIO_DIR/test_output"
JAR_PATTERN="$PROJECT_ROOT/target/urbanev-*.jar"
GENERATE_SCRIPT="$SCRIPT_DIR/generate_test_scenario.py"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate_test_output.py"

SKIP_BUILD=false
SKIP_SIM=false

for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --skip-sim)   SKIP_SIM=true  ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: bash run_integration_test.sh [--skip-build] [--skip-sim]"
            exit 1
            ;;
    esac
done

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

# ── Step 0: Generate test scenario files ─────────────────────────────────────
info "Step 0: Generating test scenario files..."
if [ ! -f "$GENERATE_SCRIPT" ]; then
    fail "generate_test_scenario.py not found at: $GENERATE_SCRIPT"
fi

python3 "$GENERATE_SCRIPT" --output-dir "$SCENARIO_DIR" 2>&1 | sed 's/^/  /'

# Verify expected files exist
for f in test_network.xml test_vehicletypes.xml test_evehicles.xml \
          test_chargers.xml test_plans.xml test_config.xml; do
    [ -f "$SCENARIO_DIR/$f" ] || fail "Expected file not generated: $SCENARIO_DIR/$f"
done
ok "Test scenario files generated in $SCENARIO_DIR"

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

# ── Locate the JAR ────────────────────────────────────────────────────────────
JAR_FILE=$(ls $JAR_PATTERN 2>/dev/null | grep -v sources | head -1 || true)
if [ -z "$JAR_FILE" ]; then
    fail "No JAR found matching: $JAR_PATTERN"
fi
info "Using JAR: $JAR_FILE"

# ── Step 2: Run simulation ────────────────────────────────────────────────────
if [ "$SKIP_SIM" = false ]; then
    info "Step 2: Running 15-iteration integration simulation..."
    rm -rf "$OUTPUT_DIR"

    # Run from SCENARIO_DIR so relative paths in config.xml (test_output, etc.) resolve correctly
    # Heap: 4 GB should be sufficient for the 50-agent test.
    # --add-opens flags required for Guice CGLIB proxy generation on JDK 17+.
    cd "$SCENARIO_DIR"
    java -Xmx4g \
         --add-opens java.base/java.lang=ALL-UNNAMED \
         --add-opens java.base/java.util=ALL-UNNAMED \
         --add-opens java.base/java.lang.invoke=ALL-UNNAMED \
         -cp "$JAR_FILE" \
         se.got.GotEVMain \
         "test_config.xml" \
         0 \
         2>&1 | tee "$SCRIPT_DIR/integration_test_sim.log" | grep -E "^(INFO|WARN|ERROR|Exception|it\.|Iteration)" | tail -60
    cd "$SCRIPT_DIR"

    SIM_EXIT=${PIPESTATUS[0]}
    [ $SIM_EXIT -eq 0 ] || fail "MATSim simulation exited with code $SIM_EXIT (see integration_test_sim.log)"
    ok "Simulation completed successfully"
else
    info "Step 2: Skipping simulation (--skip-sim)"
fi

# ── Verify output directory exists ────────────────────────────────────────────
[ -d "$OUTPUT_DIR" ] || fail "Output directory not found: $OUTPUT_DIR"

REQUIRED_OUTPUTS=(
    "$OUTPUT_DIR/output_plans.xml.gz"
    "$OUTPUT_DIR/output_evehicles.xml"
)
for f in "${REQUIRED_OUTPUTS[@]}"; do
    [ -f "$f" ] || fail "Required output file missing: $f"
done
ok "Required output files present"

# ── Step 3: Validate assertions ───────────────────────────────────────────────
info "Step 3: Validating output against 8 assertions..."
if [ ! -f "$VALIDATE_SCRIPT" ]; then
    fail "validate_test_output.py not found at: $VALIDATE_SCRIPT"
fi

python3 "$VALIDATE_SCRIPT" \
    --output-dir "$OUTPUT_DIR" \
    --scenario-dir "$SCENARIO_DIR" \
    2>&1

VALIDATE_EXIT=$?

echo ""
if [ $VALIDATE_EXIT -eq 0 ]; then
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  INTEGRATION TEST PASSED — all assertions OK ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
else
    echo -e "${RED}══════════════════════════════════════════════${NC}"
    echo -e "${RED}  INTEGRATION TEST FAILED — see above         ${NC}"
    echo -e "${RED}══════════════════════════════════════════════${NC}"
    exit $VALIDATE_EXIT
fi
