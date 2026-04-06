import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.geom.RoundRectangle2D;
import java.awt.image.BufferedImage;
import java.io.File;

public class GenerateDiagram {
    static final int W = 2600, H = 3400;
    static final Color C_BG = new Color(248,249,250);
    static final Color C_INPUT = new Color(232,244,253), C_IB = new Color(33,150,243);
    static final Color C_PROC = new Color(255,243,224), C_PB = new Color(255,152,0);
    static final Color C_CHG = new Color(252,228,236), C_CB = new Color(233,30,99);
    static final Color C_OUT = new Color(232,245,233), C_OB = new Color(76,175,80);
    static final Color C_SIM = new Color(237,231,246), C_SB = new Color(103,58,183);

    static Graphics2D g;

    static void box(int x, int y, int w, int h, String text, Color fill, Color border) {
        g.setColor(fill);
        g.fill(new RoundRectangle2D.Float(x, y, w, h, 20, 20));
        g.setStroke(new BasicStroke(3));
        g.setColor(border);
        g.draw(new RoundRectangle2D.Float(x, y, w, h, 20, 20));
        g.setColor(Color.BLACK);
        g.setFont(new Font("SansSerif", Font.PLAIN, 16));
        drawWrapped(x + 12, y + 22, w - 24, text);
    }

    static void header(int y, String text) {
        int tw = g.getFontMetrics(new Font("SansSerif", Font.BOLD, 22)).stringWidth(text) + 40;
        int x = (W - tw) / 2;
        g.setColor(new Color(55,71,79));
        g.fill(new RoundRectangle2D.Float(x, y, tw, 36, 16, 16));
        g.setColor(Color.WHITE);
        g.setFont(new Font("SansSerif", Font.BOLD, 22));
        g.drawString(text, x + 20, y + 26);
    }

    static void arrow(int x1, int y1, int x2, int y2) {
        g.setColor(new Color(69,90,100));
        g.setStroke(new BasicStroke(3));
        g.drawLine(x1, y1, x2, y2);
        double a = Math.atan2(y2-y1, x2-x1);
        int[] xp = {x2, (int)(x2-12*Math.cos(a-0.4)), (int)(x2-12*Math.cos(a+0.4))};
        int[] yp = {y2, (int)(y2-12*Math.sin(a-0.4)), (int)(y2-12*Math.sin(a+0.4))};
        g.fillPolygon(xp, yp, 3);
    }

    static void drawWrapped(int x, int y, int maxW, String text) {
        FontMetrics fm = g.getFontMetrics();
        String[] lines = text.split("\n");
        for (String line : lines) {
            if (line.startsWith("**")) {
                g.setFont(new Font("SansSerif", Font.BOLD, 16));
                line = line.replace("**", "");
                fm = g.getFontMetrics();
            }
            String[] words = line.split(" ");
            StringBuilder cur = new StringBuilder();
            for (String w : words) {
                String test = cur.length() == 0 ? w : cur + " " + w;
                if (fm.stringWidth(test) > maxW && cur.length() > 0) {
                    g.drawString(cur.toString(), x, y);
                    y += fm.getHeight();
                    cur = new StringBuilder(w);
                } else {
                    cur = new StringBuilder(test);
                }
            }
            if (cur.length() > 0) { g.drawString(cur.toString(), x, y); y += fm.getHeight(); }
            g.setFont(new Font("SansSerif", Font.PLAIN, 16));
            fm = g.getFontMetrics();
        }
    }

    public static void main(String[] args) throws Exception {
        BufferedImage img = new BufferedImage(W, H, BufferedImage.TYPE_INT_RGB);
        g = img.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g.setColor(C_BG); g.fillRect(0, 0, W, H);

        // TITLE
        g.setColor(new Color(26,26,46));
        g.setFont(new Font("SansSerif", Font.BOLD, 32));
        g.drawString("UrbanEV-v2: Maryland + DC EV Charging Simulation Pipeline", 300, 50);
        g.setFont(new Font("SansSerif", Font.PLAIN, 20));
        g.setColor(new Color(85,85,85));
        g.drawString("362,374 EV Agents (255K BEV + 107K PHEV)  |  9.8M Link Network  |  EPSG:26985  |  MATSim 12", 420, 80);

        // 1. RAW INPUTS
        header(110, "1. RAW INPUTS");
        box(20, 170, 560, 130, "**Synthetic Population CSV**\nsynthetic_bmc_v3_with_coords.csv\n4.93 GB | 19.9M rows | 6.1M persons\nBEV + PHEV agents (has_ev=1)", C_INPUT, C_IB);
        box(600, 170, 440, 130, "**AFDC Charger Data**\nMD + DC CSVs (Mar 2026)\n1,958 chargers\n(L2 + DCFC + DCFC_TESLA)", C_INPUT, C_IB);
        box(1060, 170, 500, 130, "**OSM Road Network**\nmaryland-dc-ev-network.xml.gz\n284 MB | 4.9M nodes | 9.8M links", C_INPUT, C_IB);
        box(1580, 170, 400, 130, "**Through Stations**\n14 highway boundary\ncrossing points (MD border)", C_INPUT, C_IB);
        box(2000, 170, 580, 130, "**RTS Codebook**\nData dictionary (age_group,\nincome, mode, activity codes)", C_INPUT, C_IB);

        // 2. CONVERSION
        header(330, "2. DATA CONVERSION  (pink = our changes)");
        box(20, 390, 800, 180, "**convert_synpop_v3_to_matsim.py [NEW]**\nStreams 5GB CSV -> MATSim XMLs (EV only)\nConstructs person_id = hh_id + person_slot\nMaps age_group (13 RTS codes) -> ages\nDerives: homeCharger, betaMoney, VoT,\nriskAttitude, rangeAnxiety per agent", C_CHG, C_CB);
        box(840, 390, 740, 180, "**KEY CHANGES vs Original Script**\nhas_ev=1 (was assigned_ev=1)\nev1_make/ev1_model/ev1_type (new cols)\nPHEV support: 17 new models + specs\nj1_benefits_ev_charging -> work charger\nNetwork bbox check for external trips", C_CHG, C_CB);
        box(1600, 390, 980, 180, "**convert_afdc_to_chargers_xml.py (unchanged)**\nAFDC CSV -> chargers.xml + metadata\nWGS84 -> EPSG:26985 coordinate transform\n1,607 L2 + 283 DCFC + 68 DCFC_TESLA", C_PROC, C_PB);

        arrow(300, 300, 400, 390);
        arrow(820, 300, 820, 390);
        arrow(2090, 300, 2090, 390);

        // 3. GENERATED INPUTS
        header(600, "3. GENERATED MATSim INPUT FILES");
        box(20, 660, 470, 160, "**plans_maryland_ev.xml.gz**\n362,374 agents\n1,183,157 trips\n28.3 MB (gzipped)", C_OUT, C_OB);
        box(510, 660, 470, 160, "**electric_vehicles.xml**\n362,374 EVs | 33 types\nBEV + PHEV battery specs\n46.4 MB", C_OUT, C_OB);
        box(1000, 660, 500, 160, "**vehicletypes.xml [CHANGED]**\n33 EV types + default \"car\"\nPHEV consumption rates\nFixes PrepareForSim NPE", C_CHG, C_CB);
        box(1520, 660, 500, 160, "**urbanev_vehicletypes.xml**\n**[CHANGED - Sweden fmt]**\n49 types (was 35)\n+14 PHEV + 2 generic fallbacks", C_CHG, C_CB);
        box(2040, 660, 540, 160, "**chargers.xml**\n1,958 chargers\nL2 / DCFC / DCFC_TESLA\nEPSG:26985 coords", C_OUT, C_OB);

        arrow(400, 570, 250, 660);
        arrow(400, 570, 740, 660);
        arrow(400, 570, 1250, 660);
        arrow(400, 570, 1770, 660);
        arrow(2090, 570, 2310, 660);

        // 4. CONFIG & CODE CHANGES
        header(850, "4. CONFIGURATION & CODE CHANGES  (all pink = our fixes)");
        box(20, 910, 820, 220, "**config.xml CHANGES**\n\nroutingAlgorithm: Dijkstra -> FastAStarLandmarks\nglobal.numberOfThreads: 0 (=1!) -> 14\nflowCapacityFactor: 0.02 -> 0.06\nstorageCapacityFactor: 0.06 -> 0.18\nstuckTime: 300s -> 900s\nendTime: 168h -> 240h (10 days)", C_CHG, C_CB);
        box(860, 910, 820, 220, "**GotEVMain.java CHANGES**\n\nREMOVED forced single-thread override:\n  config.parallelEventHandling()\n    .setNumberOfThreads(1)  // KILLED PERF!\n\nNow uses config value (14 threads)\nEnables parallel routing + event handling", C_CHG, C_CB);
        box(1700, 910, 880, 220, "**JVM Tuning (Ryzen 7 2700X, 128GB)**\n\n-Xmx120g -Xms64g (max RAM utilization)\n-XX:+AlwaysPreTouch (no page faults)\n-XX:ParallelGCThreads=14\nQSim: 14 threads | Event handling: 14 threads\n--add-opens for JDK 17 Guice/CGLIB", C_PROC, C_PB);

        // 5. SIMULATION ENGINE
        header(1160, "5. UrbanEV-v2 SIMULATION ENGINE");
        box(20, 1220, 580, 260, "**MATSim Core Loop**\n(10 test / 60 production iters)\n\n1. Route Plans (FastA* 14 threads)\n2. QSim Mobsim (14 threads)\n3. Score Plans\n4. Replan (strategies)\n5. Select Best Plan\n6. Repeat", C_SIM, C_SB);
        box(620, 1220, 620, 260, "**UrbanEV Modules**\n\nEvModule -> Charging/Discharging\nMobsimScopeEventHandling\n  -> Home/Work charger generation\n  -> Range anxiety monitoring\nVehicleChargingHandler\nSmartChargingEngine", C_SIM, C_SB);
        box(1260, 1220, 620, 260, "**Strategy Modules**\n\nnonCriticalSOC:\n  SelectExpBeta 0.6\n  ChangeChargingBehaviour 0.2\n  InsertEnRouteCharging 0.2\n\ncriticalSOC:\n  ChangeCharging 0.4 | EnRoute 0.6", C_SIM, C_SB);
        box(1900, 1220, 680, 260, "**Scoring (Decision Drivers)**\n\nrangeAnxietyUtility: -6\nemptyBatteryUtility: -15\nwalkingUtility: -1\nhomeChargingUtility: +1\nsocDifferenceUtility: -4\n\nPricing: Home $0.13, L2 $0.25, DCFC $0.48", C_SIM, C_SB);

        arrow(420, 1130, 300, 1220);
        arrow(1270, 1130, 930, 1220);
        arrow(2140, 1130, 2240, 1220);

        // 6. AGENT PROFILE
        header(1510, "6. EV AGENT POPULATION PROFILE");
        box(20, 1570, 840, 170, "**362,374 EV Agents**\nBEV: 255,235 (70.4%) | PHEV: 107,139 (29.6%)\nTop: Model Y 62K, Model 3 36K, BEV(generic) 30K\nTesla: 134K (37%) | Other makes: 228K (63%)", C_OUT, C_OB);
        box(880, 1570, 840, 170, "**Home Charging Distribution**\nL2 (7.2 kW): 232,214 (64.1%)\nL1 (1.4 kW): 76,706 (21.2%)\nNo charger: 53,454 (14.7%)\nDerived from: dwelling + ownership + income", C_OUT, C_OB);
        box(1740, 1570, 840, 170, "**Heterogeneous Attributes (per-agent)**\nbetaMoney: f(income) [-50 to -1.5]\nvalueOfTime: f(income, employment)\nrangeAnxietyThreshold: f(income, age) [0.10-0.40]\nriskAttitude: neutral / moderate / averse", C_OUT, C_OB);

        // 7. PERFORMANCE
        header(1770, "7. PERFORMANCE BOTTLENECKS & FIXES");
        box(20, 1830, 1280, 190, "**BEFORE (original config)**\n\nRouting: Dijkstra + 1 thread on 9.8M links = ~210 HOURS\nEvent handling: forced to 1 thread (Java code bug)\nPrepareForSim: ~6.5 sec/person (single-threaded)\nStuck agents: 75% removed (stuckTime=300s, storageCap=0.06)", C_CHG, C_CB);
        box(1320, 1830, 1260, 190, "**AFTER (our fixes)**\n\nRouting: FastAStarLandmarks + 14 threads = ~2 HOURS (100x faster)\nEvent handling: 14 threads (config-driven)\nPrepareForSim: ~0.17 sec/person (14 threads, 38x faster)\nStuck agents: expected ~15% (stuckTime=900s, storageCap=0.18)", C_OUT, C_OB);

        // 8. OUTPUTS
        header(2050, "8. SIMULATION OUTPUTS & POST-ANALYSIS");
        box(20, 2110, 620, 200, "**Per-Iteration Files**\n\nevents.xml.gz (~156 MB)\nplans.xml.gz (~2.4 GB)\nlegHistogram (car/walk)\ntripdurations.txt\nlinkstats.txt.gz", C_OUT, C_OB);
        box(660, 2110, 620, 200, "**Convergence Metrics**\n\nscorestats.txt / .png\nmodestats.txt / .png\ntraveldistancestats.txt\nstopwatch.txt / .png\noutput_persons.csv.gz", C_OUT, C_OB);
        box(1300, 2110, 620, 200, "**EV-Specific Outputs**\n\nchargers_complete.xml\nCharger occupancy profiles\nSoC time profiles\nCharging behavior scores\nEV fleet state (per-iter)", C_OUT, C_OB);
        box(1940, 2110, 640, 200, "**Post-Analysis**\n(analyze_equity_corridors.py)\n\nequity_analysis.html\ncorridor_soc_profiles.html\ncharger_utilization.html\nCSV exports for GIS", C_PROC, C_PB);

        arrow(300, 1480, 330, 2110);
        arrow(930, 1480, 970, 2110);
        arrow(1570, 1480, 1610, 2110);
        arrow(2240, 1480, 2260, 2110);

        // 9. FIRST RUN
        header(2340, "9. FIRST COMPLETED RUN (116K agents, 60 iterations, ~26 hours)");
        box(20, 2400, 840, 170, "**Score Convergence: GOOD**\nAvg executed: -0.002 -> +0.0008\nAvg best: steadily rose to +0.0016\nStabilized iter 48+ (innovation off 80%)\nMode split: 69.2% car / 30.8% walk", C_OUT, C_OB);
        box(880, 2400, 840, 170, "**Issues Found**\n75% agents stuck & removed (too aggressive)\n5,538 \"no charger found\" errors\nCrash at iter 60: soc_histogram missing\nAvg trip distance ~49.4km (stable)", C_CHG, C_CB);
        box(1740, 2400, 840, 170, "**Fixes for Production Run**\nstuckTime: 300s -> 900s\nstorageCapacityFactor: 0.06 -> 0.18\nflowCapacityFactor: 0.02 -> 0.06 (362K)\nNew population: 362K BEV+PHEV agents", C_CHG, C_CB);

        // LEGEND
        g.setFont(new Font("SansSerif", Font.BOLD, 20));
        g.setColor(Color.BLACK);
        g.drawString("LEGEND", 1220, 2640);
        Object[][] legend = {
            {C_INPUT, C_IB, "Raw Input Data"},
            {C_PROC, C_PB, "Processing / Tools"},
            {C_CHG, C_CB, "NEW / CHANGED (our work)"},
            {C_OUT, C_OB, "Generated Outputs"},
            {C_SIM, C_SB, "Simulation Engine"}
        };
        for (int i = 0; i < legend.length; i++) {
            int lx = 200 + i * 480;
            g.setColor((Color)legend[i][0]);
            g.fill(new RoundRectangle2D.Float(lx, 2660, 50, 30, 8, 8));
            g.setStroke(new BasicStroke(2));
            g.setColor((Color)legend[i][1]);
            g.draw(new RoundRectangle2D.Float(lx, 2660, 50, 30, 8, 8));
            g.setColor(Color.BLACK);
            g.setFont(new Font("SansSerif", Font.PLAIN, 16));
            g.drawString((String)legend[i][2], lx + 60, 2682);
        }

        g.setColor(new Color(136,136,136));
        g.setFont(new Font("SansSerif", Font.ITALIC, 16));
        g.drawString("github.com/Tomal121186621/UrbanEV-MATSim-Maryland", 950, 2730);
        g.setFont(new Font("SansSerif", Font.PLAIN, 14));
        g.setColor(new Color(170,170,170));
        g.drawString("AMD Ryzen 7 2700X (16 threads)  |  128 GB RAM  |  JDK 17  |  MATSim 12.0", 800, 2760);

        g.dispose();

        // Crop to actual content
        BufferedImage cropped = img.getSubimage(0, 0, W, 2800);
        ImageIO.write(cropped, "png", new File("C:\\Users\\rtomal\\Desktop\\UrbanEV Maryland\\UrbanEV-MATSim-Maryland-main\\UrbanEV_Pipeline_Diagram.png"));
        System.out.println("Saved: UrbanEV_Pipeline_Diagram.png");
    }
}
