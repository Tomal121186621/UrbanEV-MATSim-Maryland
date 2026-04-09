import org.apache.poi.xslf.usermodel.*;
import org.apache.poi.sl.usermodel.*;
import java.awt.Color;
import java.awt.Rectangle;
import java.io.FileOutputStream;

public class GeneratePresentation {

    static final Color DARK_BLUE = new Color(26, 26, 46);
    static final Color ACCENT_BLUE = new Color(33, 150, 243);
    static final Color ACCENT_PINK = new Color(233, 30, 99);
    static final Color ACCENT_GREEN = new Color(76, 175, 80);
    static final Color ACCENT_PURPLE = new Color(103, 58, 183);
    static final Color ACCENT_ORANGE = new Color(255, 152, 0);
    static final Color WHITE = Color.WHITE;
    static final Color LIGHT_GRAY = new Color(245, 245, 245);
    static final Color DARK_GRAY = new Color(55, 55, 55);

    public static void main(String[] args) throws Exception {
        XMLSlideShow ppt = new XMLSlideShow();
        ppt.setPageSize(new java.awt.Dimension(914, 514)); // 10" x 5.63" widescreen

        // 
        // SLIDE 1: Title
        // 
        XSLFSlide slide1 = ppt.createSlide();
        addBackground(slide1, DARK_BLUE);
        addText(slide1, "UrbanEV-v2: Agent-Based EV Charging\nSimulation for Maryland + DC",
                40, 80, 834, 120, 28, WHITE, true);
        addText(slide1, "Enhanced MATSim Framework with PHEV Support,\nDynamic En-Route Charging, and Equity Analysis",
                40, 210, 834, 80, 16, new Color(180, 180, 220), false);
        addText(slide1, "130,837 EV Agents  |  9.8M Link Network  |  1,958 Chargers  |  EPSG:26985\n\n" +
                "University of Maryland  |  2025",
                40, 350, 834, 100, 12, new Color(150, 150, 180), false);

        // 
        // SLIDE 2: Original UrbanEV-v2 Overview
        // 
        XSLFSlide slide2 = ppt.createSlide();
        addBackground(slide2, WHITE);
        addText(slide2, "Original UrbanEV-v2 Framework", 40, 20, 834, 50, 24, DARK_BLUE, true);
        addText(slide2, "Developed by TU Munich / Chalmers / Gothenburg (Adenaw et al., 2020)",
                40, 60, 834, 30, 11, DARK_GRAY, false);
        addText(slide2,
            "Core Architecture (MATSim 12.0 Extension)\n" +
            "  - Agent-based co-evolutionary learning (plan selection + mutation)\n" +
            "  - QSim traffic simulation with EV battery discharge model\n" +
            "  - Charger infrastructure with plug-level queue management\n" +
            "  - Variable-speed charging curves (Tesla, Leaf, generic profiles)\n\n" +
            "Original Scoring Function\n" +
            "  - Range anxiety: penalty when SoC < threshold\n" +
            "  - Empty battery: severe penalty at SoC = 0\n" +
            "  - Walking distance: exponential decay to charger\n" +
            "  - Home charging bonus: reward for using home charger\n" +
            "  - Energy balance: penalty if end-of-day SoC < start\n\n" +
            "Original Strategies\n" +
            "  - ChangeChargingBehaviour: add/remove/move charging at destinations\n" +
            "  - SelectExpBeta: probabilistic plan selection\n" +
            "  - Two subpopulations: nonCriticalSOC / criticalSOC",
            40, 95, 834, 380, 11, DARK_GRAY, false);

        // 
        // SLIDE 3: Original Limitations
        // 
        XSLFSlide slide3 = ppt.createSlide();
        addBackground(slide3, WHITE);
        addText(slide3, "Limitations of Original UrbanEV-v2", 40, 20, 834, 50, 24, ACCENT_PINK, true);
        addText(slide3,
            "1. No En-Route Charging\n" +
            "   Agents could only charge at destinations they already visited.\n" +
            "   No mid-trip DCFC stops for long-distance trips.\n\n" +
            "2. No PHEV Support\n" +
            "   All EVs treated as battery-only. PHEVs would strand when battery depleted\n" +
            "   instead of switching to gasoline.\n\n" +
            "3. No Multi-Day SoC Persistence\n" +
            "   Battery state reset each iteration. No overnight charging model.\n\n" +
            "4. No Charging Cost Differentiation\n" +
            "   Flat pricing, no power-tier pricing, no time-of-use awareness.\n\n" +
            "5. Single-Thread Performance\n" +
            "   parallelEventHandling forced to 1 thread. Dijkstra routing.\n\n" +
            "6. No Charger Reliability / Workplace Competition\n" +
            "   All chargers 100% available. Private per-agent work chargers.",
            40, 75, 834, 400, 11, DARK_GRAY, false);

        // 
        // SLIDE 4: Our Contributions Overview
        // 
        XSLFSlide slide4 = ppt.createSlide();
        addBackground(slide4, WHITE);
        addText(slide4, "Our Contributions: 12 Major Enhancements", 40, 20, 834, 50, 24, ACCENT_GREEN, true);
        addText(slide4,
            "New Simulation Features (Java)\n" +
            "  1. InsertEnRouteCharging strategy (DCFC preference, dynamic duration)\n" +
            "  2. PHEV gas fallback (CD/CS mode at 15% SoC)\n" +
            "  3. Multi-day SoC persistence with overnight home charging\n" +
            "  4. Workplace charger competition (shared pools, 1:5 ratio)\n" +
            "  5. Charging cost awareness (softmax cost-weighted selection)\n" +
            "  6. Charger reliability/downtime (80% DCFC, 92% L2 uptime)\n\n" +
            "Scoring Calibration (Literature-Backed)\n" +
            "  7. betaMoney: sqrt income elasticity (Kickhofer et al. 2011)\n" +
            "  8. emptyBatteryUtility: -15 to -40 (NREL BEAM)\n" +
            "  9. homeChargingUtility: +1 to +2.5 (Ge et al. 2023)\n" +
            "  10. Walking disutility recalibration (Geurs & van Wee 2004)\n\n" +
            "Performance & Infrastructure\n" +
            "  11. FastAStarLandmarks + 14 parallel threads (100x speedup)\n" +
            "  12. Queue traffic dynamics (fixes 95% stuck agent rate)",
            40, 75, 834, 400, 11, DARK_GRAY, false);

        // 
        // SLIDE 5: En-Route Charging
        // 
        XSLFSlide slide5 = ppt.createSlide();
        addBackground(slide5, WHITE);
        addText(slide5, "Feature 1: Dynamic En-Route Charging", 40, 20, 834, 50, 24, ACCENT_PURPLE, true);
        addText(slide5,
            "Problem: Agents with long trips run out of battery mid-drive.\n" +
            "Original UrbanEV had no mechanism to add charging stops along routes.\n\n" +
            "Our Solution: InsertEnRouteChargingModule\n\n" +
            "Pipeline per agent:\n" +
            "  1. SocProblemCollector records agents with SoC < threshold\n" +
            "  2. For each problem, find the car leg where battery depleted\n" +
            "  3. Scan route links for chargers (DCFC preferred, L2 fallback)\n" +
            "  4. Select charger based on risk attitude:\n" +
            "     - risk_averse: earliest 25% of route (charge early, bigger buffer)\n" +
            "     - moderate: middle 50% (balanced)\n" +
            "     - risk_neutral: latest 25% (push battery further)\n" +
            "  5. Calculate dynamic duration from remaining distance + energy need\n" +
            "     + safety buffer (averse 30%, moderate 15%, seeking 5%)\n" +
            "  6. Split leg: [drive] -> [charge at DCFC] -> [drive]\n\n" +
            "Results: 5,054 insertions in iteration 1, 85% DCFC, 15% L2 fallback\n" +
            "Duration range: 5 min (quick top-up) to 22 min (long trip, 62.5 kW DCFC)",
            40, 75, 834, 400, 10, DARK_GRAY, false);

        // 
        // SLIDE 6: PHEV + SoC Persistence
        // 
        XSLFSlide slide6 = ppt.createSlide();
        addBackground(slide6, WHITE);
        addText(slide6, "Features 2-3: PHEV Gas Fallback + SoC Persistence", 40, 20, 834, 50, 24, ACCENT_PURPLE, true);
        addText(slide6,
            "PHEV Gas Fallback (Axsen et al. 2020; Raghavan & Tal 2020)\n\n" +
            "  PHEVs switch to gasoline at 15% SoC (configurable)\n" +
            "  Gasoline consumption: energy / (34.2 MJ/L x 0.30 efficiency)\n" +
            "  Tracks gas usage per vehicle for cost scoring\n" +
            "  40K PHEV agents (30% of fleet) now behave realistically\n\n" +
            "Multi-Day SoC Persistence (Baum et al. 2022)\n\n" +
            "  End-of-iteration SoC carried to next iteration's initial SoC\n" +
            "  Overnight home charging model (NREL 2023; INL 2015):\n" +
            "    - SoC-dependent plug-in probability:\n" +
            "      SoC < 30%: 95% | 30-50%: 85% | 50-70%: 65% | >90%: 10%\n" +
            "    - Produces 72% nightly plug-in rate (matches INL observed 70-75%)\n" +
            "    - Target SoC by vehicle type:\n" +
            "      Tesla: 80% (60%), 90% (25%), 100% (15%)\n" +
            "      Non-Tesla BEV: 80% (40%), 90% (25%), 100% (35%)\n" +
            "      PHEV: 100% always (Xu et al. 2023, Nature Energy)\n" +
            "    - L1 max 11 kWh overnight | L2 max 58 kWh\n" +
            "    - No-home-charger agents (19%): no overnight recovery",
            40, 75, 834, 400, 10, DARK_GRAY, false);

        // 
        // SLIDE 7: Workplace + Cost + Reliability
        // 
        XSLFSlide slide7 = ppt.createSlide();
        addBackground(slide7, WHITE);
        addText(slide7, "Features 4-6: Workplace, Cost Awareness, Reliability", 40, 20, 834, 50, 24, ACCENT_PURPLE, true);
        addText(slide7,
            "Workplace Charger Competition (Wood et al. 2018, NREL)\n" +
            "  - Replaces per-agent private chargers with shared pools\n" +
            "  - Clustered by 500m grid | 1 plug per 5 EV workers\n" +
            "  - 2,989 shared pools from 11,537 EV workers\n" +
            "  - First-come-first-served queue with retry\n\n" +
            "Charging Cost Awareness (Ge et al. 2023; Chakraborty et al. 2020)\n" +
            "  - Softmax cost-weighted charger selection\n" +
            "  - weight = exp(-beta x cost_per_kWh)\n" +
            "  - Work (free) >> Home ($0.13) >> Public L2 ($0.25) >> DCFC ($0.48)\n" +
            "  - Income-sensitive via betaMoney (sqrt elasticity)\n\n" +
            "Charger Reliability (Rempel et al. 2022, NREL TP-5400-83459)\n" +
            "  - Per-plug stochastic downtime each iteration\n" +
            "  - DCFC: 80% uptime | L2: 92% uptime (national averages)\n" +
            "  - ~9% plugs disabled, ~280 chargers offline per iteration\n" +
            "  - Private home chargers: always available\n" +
            "  - Agents learn to cope through evolutionary replanning",
            40, 75, 834, 400, 10, DARK_GRAY, false);

        // 
        // SLIDE 8: Scoring Calibration
        // 
        XSLFSlide slide8 = ppt.createSlide();
        addBackground(slide8, WHITE);
        addText(slide8, "Scoring Parameter Calibration", 40, 20, 834, 50, 24, ACCENT_ORANGE, true);
        addText(slide8,
            "8 Scoring Components (per agent, per activity)\n\n" +
            "Component          Original    Calibrated  Source\n" +
            "-------------------------------------------------------\n" +
            "Range Anxiety        -5.0        -6.0      Dong & Lin 2020\n" +
            "Empty Battery       -10.0       -40.0      NREL BEAM\n" +
            "Walking Dist.        -1.0        -2.5      Charypar-Nagel\n" +
            "Home Charging        +1.0        +2.5      Ge et al. 2023\n" +
            "Energy Balance      -10.0        -4.0      Baum et al. 2022\n" +
            "Charging Cost       flat     power-tier    MD electricity rates\n" +
            "Detour Time           --        -6.0/hr    Axhausen et al.\n" +
            "Queue Wait            --     VoT x 2.0     Lee & Small 2022\n" +
            "Gasoline Cost         --     betaMoney      Axsen et al. 2020\n\n" +
            "betaMoney Formula (Kickhofer et al. 2011, TRB)\n" +
            "  Old: -6.0 x (62500 / income)     -- range -50 to -1.5\n" +
            "  New: -1.0 x sqrt(125000 / income) -- range -4.1 to -0.5\n" +
            "  Reference income: $125K (actual median of MD EV agents)\n" +
            "  Consistent with MATSim marginalUtilityOfMoney = 1.0",
            40, 70, 834, 410, 10, DARK_GRAY, false);

        // 
        // SLIDE 9: Maryland Data Pipeline
        // 
        XSLFSlide slide9 = ppt.createSlide();
        addBackground(slide9, WHITE);
        addText(slide9, "Maryland + DC Data Pipeline", 40, 20, 834, 50, 24, ACCENT_BLUE, true);
        addText(slide9,
            "Input Data\n" +
            "  - Synthetic population: 19.9M rows, 6.1M persons (BMC v3 + VAE model)\n" +
            "  - OSM road network: 4.9M nodes, 9.8M links, 284 MB compressed\n" +
            "  - AFDC charger data: 1,958 chargers (1,607 L2 + 283 DCFC + 68 Tesla)\n" +
            "  - RTS codebook: 13 age groups, 10 income brackets, 15 travel modes\n\n" +
            "Household-Level EV Assignment\n" +
            "  - 362,374 persons with has_ev=1 -> 142,754 actual EVs (ev_count)\n" +
            "  - Top ev_count drivers per household get EV assignment\n" +
            "  - Primary driver: ev1 specs from CSV | Secondary: generic BEV/PHEV\n" +
            "  - Skip walk-only agents (158K) and no-EV-slot agents (73K)\n" +
            "  - Final: 130,837 driving EV agents (91K BEV + 40K PHEV)\n\n" +
            "Derived Agent Attributes\n" +
            "  - homeChargerPower: f(dwelling, ownership, income) -- 59% L2, 22% L1, 19% none\n" +
            "  - betaMoney: -1.0 x sqrt(125000/income) -- income-sensitive\n" +
            "  - rangeAnxietyThreshold: f(income, age) -- 0.10 to 0.40\n" +
            "  - riskAttitude: neutral/moderate/averse -- f(income, age)\n" +
            "  - 14 through stations for external trip boundary snapping",
            40, 70, 834, 410, 10, DARK_GRAY, false);

        // 
        // SLIDE 10: Performance
        // 
        XSLFSlide slide10 = ppt.createSlide();
        addBackground(slide10, WHITE);
        addText(slide10, "Performance Optimization", 40, 20, 834, 50, 24, ACCENT_BLUE, true);
        addText(slide10,
            "Bottleneck              Before              After            Speedup\n" +
            "------------------------------------------------------------------------\n" +
            "Routing algorithm    Dijkstra (1 thread)  FastAStarLandmarks   ~100x\n" +
            "                                          (14 threads)\n" +
            "PrepareForSim        6.5 sec/person       0.17 sec/person      ~38x\n" +
            "Event handling       1 thread (forced!)   14 threads            ~14x\n" +
            "Traffic dynamics     kinematicWaves       queue                 fixes\n" +
            "                     (95% stuck on        (0.04% stuck)         stuck\n" +
            "                     short links)\n\n" +
            "Root Cause Analysis\n" +
            "  - GotEVMain.java forced parallelEventHandling.setNumberOfThreads(1)\n" +
            "  - Global numberOfThreads=0 meant single-threaded, not auto-detect\n" +
            "  - 65% of network links < 20m caused kinematic wave storage gridlock\n" +
            "  - SmartChargingScheduler ConcurrentModificationException in retry loop\n\n" +
            "Hardware: AMD Ryzen 7 2700X (16 threads), 128 GB RAM, JDK 17\n" +
            "Runtime: ~80 min/iteration for 130K agents on 9.8M link network",
            40, 70, 834, 410, 10, DARK_GRAY, false);

        // 
        // SLIDE 11: Equity & Population
        // 
        XSLFSlide slide11 = ppt.createSlide();
        addBackground(slide11, WHITE);
        addText(slide11, "Agent Population & Equity Profile", 40, 20, 834, 50, 24, ACCENT_GREEN, true);
        addText(slide11,
            "Home Charger Distribution\n" +
            "  L2 (7.2 kW): 76,787 (59%) | L1 (1.4 kW): 29,333 (22%) | None: 24,717 (19%)\n\n" +
            "Equity Findings (Per-Component Scoring, Iteration 5)\n\n" +
            "Agent Group          Score   Range Anxiety  Empty Battery  Home Bonus\n" +
            "------------------------------------------------------------------------\n" +
            "Has charger + uses   -0.51     -0.60          -0.83         +1.07\n" +
            "Has charger, unused  -2.02     -0.83          -1.05          0.00\n" +
            "NO home charger     -10.46     -2.68          -7.59         +0.17\n\n" +
            "Key Equity Insights\n" +
            "  - No-charger agents score 20x worse than home-charger agents\n" +
            "  - 69% of <$25K agents have no home charger\n" +
            "  - 85% of renters have no home charger\n" +
            "  - 100% of apartment dwellers have no home charger\n" +
            "  - These 24,717 agents are entirely dependent on public infrastructure\n" +
            "  - Charger gap locations: 120 'no charger on route' warnings",
            40, 70, 834, 410, 10, DARK_GRAY, false);

        // 
        // SLIDE 12: Results & Outputs
        // 
        XSLFSlide slide12 = ppt.createSlide();
        addBackground(slide12, WHITE);
        addText(slide12, "Simulation Results & Research Outputs", 40, 20, 834, 50, 24, ACCENT_BLUE, true);
        addText(slide12,
            "Iteration 5 Charging Behavior (with all enhancements)\n\n" +
            "  Charger Type     Sessions    Avg kWh    Avg Power\n" +
            "  -------------------------------------------------\n" +
            "  Public            16,726      3.7 kWh    11.2 kW\n" +
            "  Home               8,562      2.5 kWh     6.2 kW\n" +
            "  Work               8,142     11.1 kWh    12.7 kW\n\n" +
            "  En-route insertions: 5,054 (iter 1) | 85% DCFC, 15% L2\n" +
            "  Overnight plug-in rate: 72% (matches NREL observed 70-75%)\n\n" +
            "Potential Research Studies\n" +
            "  1. Charger infrastructure gap analysis (unmet demand mapping)\n" +
            "  2. Income-stratified charging equity assessment\n" +
            "  3. Grid load profiles (24-hr charging demand curves)\n" +
            "  4. PHEV vs BEV electrification rates\n" +
            "  5. Home charger penetration impact analysis\n" +
            "  6. Charger utilization & revenue modeling\n" +
            "  7. Range anxiety geography (corridor-level SoC profiles)\n" +
            "  8. Vehicle fleet composition impact on infrastructure needs",
            40, 70, 834, 410, 10, DARK_GRAY, false);

        // 
        // SLIDE 13: Thank You
        // 
        XSLFSlide slide13 = ppt.createSlide();
        addBackground(slide13, DARK_BLUE);
        addText(slide13, "Thank You", 40, 100, 834, 80, 36, WHITE, true);
        addText(slide13, "github.com/Tomal121186621/UrbanEV-MATSim-Maryland",
                40, 220, 834, 40, 14, new Color(180, 180, 220), false);
        addText(slide13,
            "130,837 EV Agents  |  33 Vehicle Types (BEV + PHEV)\n" +
            "9.8M Link Network  |  1,958 Chargers  |  14 Through Stations\n" +
            "8 Scoring Components  |  3 Replanning Strategies  |  6 New Features\n\n" +
            "Built on MATSim 12.0 + UrbanEV-v2 (TU Munich / Chalmers)",
            40, 300, 834, 120, 12, new Color(150, 150, 180), false);

        // Save
        String path = "C:\\Users\\rtomal\\Desktop\\UrbanEV Maryland\\UrbanEV-MATSim-Maryland-main\\UrbanEV_Presentation.pptx";
        FileOutputStream out = new FileOutputStream(path);
        ppt.write(out);
        out.close();
        ppt.close();
        System.out.println("Saved: " + path);
    }

    static void addBackground(XSLFSlide slide, Color color) {
        XSLFAutoShape bg = slide.createAutoShape();
        bg.setAnchor(new Rectangle(0, 0, 914, 514));
        bg.setFillColor(color);
        bg.setLineColor(color);
    }

    static void addText(XSLFSlide slide, String text, int x, int y, int w, int h,
                        int fontSize, Color color, boolean bold) {
        XSLFTextBox box = slide.createTextBox();
        box.setAnchor(new Rectangle(x, y, w, h));
        box.clearText();
        XSLFTextParagraph para = box.addNewTextParagraph();

        String[] lines = text.split("\n");
        for (int i = 0; i < lines.length; i++) {
            if (i > 0) para = box.addNewTextParagraph();
            XSLFTextRun run = para.addNewTextRun();
            run.setText(lines[i]);
            run.setFontSize((double) fontSize);
            run.setFontColor(color);
            run.setBold(bold);
            run.setFontFamily("Calibri");
        }
    }
}
