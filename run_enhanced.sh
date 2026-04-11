#!/bin/bash
# ============================================================================
# Run ENHANCED model (UrbanEV-v2 + Maryland extensions)
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  UrbanEV-v2 ENHANCED Model"
echo "  + En-route charging"
echo "  + PHEV gas fallback"
echo "  + SoC persistence"
echo "  + Workplace charger competition"
echo "  + Charger reliability"
echo "  + Charypar-Nagel combined scoring"
echo "========================================="

# Build enhanced model
echo "[1/2] Building enhanced model..."
cd enhanced_model
mvn clean package -DskipTests -Denforcer.skip=true -q
cd ..

# Determine available RAM
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 131072000)
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
XMX=$((TOTAL_RAM_GB * 3 / 4))
if [ "$XMX" -gt 96 ]; then XMX=96; fi
if [ "$XMX" -lt 8 ]; then XMX=8; fi

echo "[2/2] Running enhanced simulation (Xmx=${XMX}g)..."
java -Xmx${XMX}g -Xms${XMX}g \
    --add-opens java.base/java.lang=ALL-UNNAMED \
    --add-opens java.base/java.util=ALL-UNNAMED \
    --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
    --add-opens java.base/java.text=ALL-UNNAMED \
    --add-opens java.desktop/java.awt.font=ALL-UNNAMED \
    -cp "enhanced_model/target/*:enhanced_model/target/dependency/*" \
    se.got.GotEVMain enhanced_model/config_enhanced.xml \
    2>&1 | tee output_enhanced/enhanced_simulation.log

echo "Done. Output in output_enhanced/"
