#!/usr/bin/env bash
# Auto-validation: run comprehensive validation after iterations 5, 10, 15, 20, ...
# Generates dashboard, updates results PPTX, pushes to GitHub.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="/c/ProgramData/anaconda3/python.exe"
LOG_FILE="full_simulation.log"
LAST_VALIDATED=-1

echo "Auto-validation monitor started."
echo "Will validate at iterations 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60"

while true; do
    CURRENT_ITER=$(grep -c "ITERATION.*ENDS" "$LOG_FILE" 2>/dev/null || echo 0)

    # Check if we've hit a validation milestone (every 5 iterations)
    MILESTONE=$((CURRENT_ITER / 5 * 5))

    if [ "$MILESTONE" -ge 5 ] && [ "$MILESTONE" -gt "$LAST_VALIDATED" ]; then
        ITER_NUM=$((CURRENT_ITER - 1))
        EVENTS_FILE="output/maryland_ev_enhanced/ITERS/it.${MILESTONE}/maryland_ev_v2.${MILESTONE}.events.xml.gz"

        if [ -f "$EVENTS_FILE" ]; then
            echo ""
            echo "=========================================="
            echo "VALIDATION at iteration $MILESTONE"
            echo "=========================================="

            # Run validation
            echo "Running validation..."
            $PYTHON validate_simulation.py 2>&1 | tail -20

            # Run analysis dashboards
            echo "Running analysis dashboard..."
            $PYTHON generate_analysis.py 2>&1 | tail -5

            echo "Running detailed analysis..."
            $PYTHON generate_detailed_analysis.py 2>&1 | tail -5

            echo "Running deep analysis..."
            $PYTHON generate_deep_analysis.py 2>&1 | tail -5

            # Update results PPTX
            echo "Updating results PPTX..."
            $PYTHON generate_results_pptx.py 2>&1 | tail -3

            # Commit and push
            echo "Pushing to GitHub..."
            git add analysis_output/ validation_data/ UrbanEV_Results.pptx 2>/dev/null
            git commit -m "Auto-validation after iteration $MILESTONE ($(date '+%Y-%m-%d %H:%M'))" 2>/dev/null
            git push origin main 2>/dev/null

            LAST_VALIDATED=$MILESTONE
            echo "Done. Next validation at iteration $((MILESTONE + 5))"
        fi
    fi

    sleep 120
done
