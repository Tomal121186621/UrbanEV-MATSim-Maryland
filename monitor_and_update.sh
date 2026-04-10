#!/usr/bin/env bash
# Monitor simulation, regenerate results PPTX after each iteration, push to GitHub.
# Usage: bash monitor_and_update.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="/c/ProgramData/anaconda3/python.exe"
LOG_FILE="full_simulation.log"
LAST_ITER=-1

echo "Monitoring simulation for iteration completions..."
echo "Will regenerate UrbanEV_Results.pptx and push to GitHub after each iteration."

while true; do
    # Count completed iterations
    CURRENT_ITER=$(grep -c "ITERATION.*ENDS" "$LOG_FILE" 2>/dev/null || echo 0)

    if [ "$CURRENT_ITER" -gt "$LAST_ITER" ]; then
        ITER_NUM=$((CURRENT_ITER - 1))
        echo ""
        echo "=== Iteration $ITER_NUM completed ==="
        echo "Generating results PPTX..."

        $PYTHON generate_results_pptx.py

        echo "Committing and pushing to GitHub..."
        git add UrbanEV_Results.pptx generate_results_pptx.py
        git commit -m "Auto-update results after iteration $ITER_NUM" --allow-empty 2>/dev/null || true
        git push origin main 2>/dev/null || echo "Push failed (will retry next iteration)"

        LAST_ITER=$CURRENT_ITER
        echo "Done. Waiting for next iteration..."
    fi

    sleep 120  # Check every 2 minutes
done
