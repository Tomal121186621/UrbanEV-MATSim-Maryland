#!/bin/bash
# ============================================================================
# Run BASELINE model (original UrbanEV-v2, no en-route charging)
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  UrbanEV-v2 BASELINE Model"
echo "  Original framework (Parishwad et al.)"
echo "  No en-route charging, no PHEV"
echo "========================================="

# Build baseline model
echo "[1/2] Building baseline model..."
cd baseline_model
mvn clean package -DskipTests -Denforcer.skip=true -q
cd ..

# Determine available RAM
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 131072000)
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
XMX=$((TOTAL_RAM_GB * 3 / 4))
if [ "$XMX" -gt 96 ]; then XMX=96; fi
if [ "$XMX" -lt 8 ]; then XMX=8; fi

echo "[2/2] Running baseline simulation (Xmx=${XMX}g)..."
java -Xmx${XMX}g -Xms${XMX}g \
    --add-opens java.base/java.lang=ALL-UNNAMED \
    --add-opens java.base/java.util=ALL-UNNAMED \
    --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
    --add-opens java.base/java.text=ALL-UNNAMED \
    --add-opens java.desktop/java.awt.font=ALL-UNNAMED \
    -cp "baseline_model/target/*:baseline_model/target/dependency/*" \
    se.got.GotEVMain baseline_model/config_baseline.xml \
    2>&1 | tee output_baseline/baseline_simulation.log

echo "Done. Output in output_baseline/"
