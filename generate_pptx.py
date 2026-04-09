#!/usr/bin/env python3
"""Generate UrbanEV presentation as PPTX using raw Office Open XML (no dependencies)."""
import zipfile
import os

# PPTX is a ZIP with XML files inside
OUTPUT = "UrbanEV_Presentation.pptx"

# ── Slide content ─────────────────────────────────────────────────────────────

SLIDES = [
    # (title, subtitle, body, title_color_hex, bg_dark)
    (
        "UrbanEV-v2: Agent-Based EV Charging\nSimulation for Maryland + DC",
        "Enhanced MATSim Framework with PHEV Support,\nDynamic En-Route Charging, and Equity Analysis",
        "130,837 EV Agents  |  9.8M Link Network  |  1,958 Chargers  |  EPSG:26985\nUniversity of Maryland  |  2025",
        "FFFFFF", True
    ),
    (
        "Original UrbanEV-v2 Framework",
        "Developed by TU Munich / Chalmers / Gothenburg (Adenaw et al., 2020)",
        "Core Architecture (MATSim 12.0 Extension)\n"
        "  - Agent-based co-evolutionary learning (plan selection + mutation)\n"
        "  - QSim traffic simulation with EV battery discharge model\n"
        "  - Charger infrastructure with plug-level queue management\n"
        "  - Variable-speed charging curves (Tesla, Leaf, generic profiles)\n\n"
        "Original Scoring Function\n"
        "  - Range anxiety: penalty when SoC < threshold\n"
        "  - Empty battery: severe penalty at SoC = 0\n"
        "  - Walking distance: exponential decay to charger\n"
        "  - Home charging bonus: reward for using home charger\n"
        "  - Energy balance: penalty if end-of-day SoC < start\n\n"
        "Original Strategies\n"
        "  - ChangeChargingBehaviour: add/remove/move charging at destinations\n"
        "  - SelectExpBeta: probabilistic plan selection\n"
        "  - Two subpopulations: nonCriticalSOC / criticalSOC",
        "1A1A2E", False
    ),
    (
        "Limitations of Original UrbanEV-v2",
        "",
        "1. No En-Route Charging\n"
        "   Agents could only charge at destinations they already visited.\n"
        "   No mid-trip DCFC stops for long-distance trips.\n\n"
        "2. No PHEV Support\n"
        "   All EVs treated as battery-only. PHEVs strand when battery depleted.\n\n"
        "3. No Multi-Day SoC Persistence\n"
        "   Battery state reset each iteration. No overnight charging model.\n\n"
        "4. No Charging Cost Differentiation\n"
        "   Flat pricing, no power-tier pricing, no time-of-use awareness.\n\n"
        "5. Single-Thread Performance\n"
        "   parallelEventHandling forced to 1 thread. Dijkstra routing.\n\n"
        "6. No Charger Reliability / Workplace Competition\n"
        "   All chargers 100% available. Private per-agent work chargers.",
        "E91E63", False
    ),
    (
        "Our Contributions: 12 Major Enhancements",
        "",
        "New Simulation Features (Java)\n"
        "  1. InsertEnRouteCharging strategy (DCFC preference, dynamic duration)\n"
        "  2. PHEV gas fallback (CD/CS mode at 15% SoC)\n"
        "  3. Multi-day SoC persistence with overnight home charging\n"
        "  4. Workplace charger competition (shared pools, 1:5 ratio)\n"
        "  5. Charging cost awareness (softmax cost-weighted selection)\n"
        "  6. Charger reliability/downtime (80% DCFC, 92% L2 uptime)\n\n"
        "Scoring Calibration (Literature-Backed)\n"
        "  7. betaMoney: sqrt income elasticity (Kickhofer et al. 2011)\n"
        "  8. emptyBatteryUtility: -15 to -40 (NREL BEAM)\n"
        "  9. homeChargingUtility: +1 to +2.5 (Ge et al. 2023)\n"
        "  10. Walking disutility recalibration (Geurs & van Wee 2004)\n\n"
        "Performance & Infrastructure\n"
        "  11. FastAStarLandmarks + 14 parallel threads (100x speedup)\n"
        "  12. Queue traffic dynamics (fixes 95% stuck agent rate)",
        "4CAF50", False
    ),
    (
        "Feature 1: Dynamic En-Route Charging",
        "",
        "Problem: Agents with long trips run out of battery mid-drive.\n\n"
        "Our Solution: InsertEnRouteChargingModule\n\n"
        "Pipeline per agent:\n"
        "  1. SocProblemCollector records agents with SoC < threshold\n"
        "  2. Find the car leg where battery depleted\n"
        "  3. Scan route for chargers (DCFC preferred, L2 fallback)\n"
        "  4. Select charger based on risk attitude:\n"
        "     risk_averse: earliest 25% | moderate: middle 50% | risk_neutral: latest 25%\n"
        "  5. Dynamic duration from remaining distance + energy need + safety buffer\n"
        "  6. Split leg: [drive] -> [charge at DCFC] -> [drive]\n\n"
        "Results: 5,054 insertions in iteration 1\n"
        "  85% DCFC, 15% L2 fallback\n"
        "  Duration: 5 min (quick top-up) to 22 min (long trip)",
        "673AB7", False
    ),
    (
        "Features 2-3: PHEV Gas Fallback + SoC Persistence",
        "",
        "PHEV Gas Fallback (Axsen et al. 2020; Raghavan & Tal 2020)\n"
        "  - PHEVs switch to gasoline at 15% SoC (configurable)\n"
        "  - Gasoline consumption: energy / (34.2 MJ/L x 0.30 efficiency)\n"
        "  - 40K PHEV agents (30% of fleet) now behave realistically\n\n"
        "Multi-Day SoC Persistence (Baum et al. 2022)\n"
        "  - End-of-iteration SoC carried to next iteration\n"
        "  - Overnight home charging model (NREL 2023; INL 2015):\n"
        "    SoC-dependent plug-in probability:\n"
        "      <30%: 95% | 30-50%: 85% | 50-70%: 65% | >90%: 10%\n"
        "    Produces 72% nightly plug-in rate (matches INL 70-75%)\n"
        "    Target SoC: Tesla 80%(60%)/90%(25%)/100%(15%)\n"
        "    Non-Tesla: 80%(40%)/90%(25%)/100%(35%) | PHEV: 100%\n"
        "    L1 max 11 kWh | L2 max 58 kWh overnight\n"
        "    No-home-charger agents (19%): no overnight recovery",
        "673AB7", False
    ),
    (
        "Features 4-6: Workplace, Cost Awareness, Reliability",
        "",
        "Workplace Charger Competition (Wood et al. 2018, NREL)\n"
        "  - Shared pools: 1 plug per 5 EV workers (replaces per-agent private)\n"
        "  - 2,989 pools from 11,537 EV workers | First-come-first-served\n\n"
        "Charging Cost Awareness (Ge et al. 2023; Chakraborty et al. 2020)\n"
        "  - Softmax cost-weighted selection: weight = exp(-beta x cost)\n"
        "  - Work (free) >> Home ($0.13) >> Public L2 ($0.25) >> DCFC ($0.48)\n\n"
        "Charger Reliability (Rempel et al. 2022, NREL TP-5400-83459)\n"
        "  - Per-plug stochastic downtime each iteration\n"
        "  - DCFC: 80% uptime | L2: 92% uptime | Home: always available\n"
        "  - ~9% plugs disabled, ~280 chargers offline per iteration",
        "673AB7", False
    ),
    (
        "Scoring Parameter Calibration",
        "",
        "Component          Original    Calibrated    Source\n"
        "-----------------------------------------------------------\n"
        "Range Anxiety        -5.0        -6.0        Dong & Lin 2020\n"
        "Empty Battery       -10.0       -40.0        NREL BEAM\n"
        "Walking Dist.        -1.0        -2.5        Charypar-Nagel\n"
        "Home Charging        +1.0        +2.5        Ge et al. 2023\n"
        "Energy Balance      -10.0        -4.0        Baum et al. 2022\n"
        "Charging Cost       flat      power-tier     MD rates\n"
        "Detour Time           --        -6.0/hr      Axhausen et al.\n"
        "Queue Wait            --       VoT x 2.0     Lee & Small 2022\n\n"
        "betaMoney Formula (Kickhofer et al. 2011, TRB)\n"
        "  Old: -6.0 x (62500 / income)     range -50 to -1.5\n"
        "  New: -1.0 x sqrt(125000 / income) range -4.1 to -0.5\n"
        "  Reference: $125K (actual median of MD EV agents)",
        "FF9800", False
    ),
    (
        "Maryland + DC Data Pipeline",
        "",
        "Input Data\n"
        "  - Synthetic population: 19.9M rows, 6.1M persons (BMC v3)\n"
        "  - OSM road network: 4.9M nodes, 9.8M links, 284 MB\n"
        "  - AFDC chargers: 1,958 (1,607 L2 + 283 DCFC + 68 Tesla)\n\n"
        "Household-Level EV Assignment\n"
        "  - 362K has_ev=1 persons -> 142,754 actual EVs (ev_count)\n"
        "  - Top drivers per household get EV | Secondary: generic type\n"
        "  - Final: 130,837 agents (91K BEV + 40K PHEV)\n\n"
        "Derived Attributes\n"
        "  - homeChargerPower: f(dwelling, ownership, income)\n"
        "    59% L2, 22% L1, 19% none\n"
        "  - betaMoney: -1.0 x sqrt(125000/income)\n"
        "  - rangeAnxietyThreshold: f(income, age) [0.10-0.40]\n"
        "  - riskAttitude: neutral/moderate/averse",
        "2196F3", False
    ),
    (
        "Performance Optimization",
        "",
        "Bottleneck           Before                After              Speedup\n"
        "----------------------------------------------------------------------\n"
        "Routing            Dijkstra (1 thread)   FastAStarLandmarks    ~100x\n"
        "                                         (14 threads)\n"
        "PrepareForSim      6.5 sec/person        0.17 sec/person       ~38x\n"
        "Event handling     1 thread (forced!)     14 threads            ~14x\n"
        "Traffic dynamics   kinematicWaves         queue                 fixes\n"
        "                   (95% stuck)            (0.04% stuck)         stuck\n\n"
        "Root Causes Found\n"
        "  - GotEVMain forced parallelEventHandling to 1 thread\n"
        "  - numberOfThreads=0 meant single-threaded, not auto-detect\n"
        "  - 65% of network links < 20m: kinematic wave storage gridlock\n"
        "  - SmartChargingScheduler ConcurrentModificationException\n\n"
        "Hardware: Ryzen 7 2700X (16 threads), 128 GB RAM, JDK 17",
        "2196F3", False
    ),
    (
        "Agent Population & Equity Profile",
        "",
        "Home Charger Distribution\n"
        "  L2 (7.2 kW): 76,787 (59%) | L1 (1.4 kW): 29,333 (22%) | None: 24,717 (19%)\n\n"
        "Per-Component Scoring (Iteration 5)\n"
        "  Agent Group           Score   Empty Battery  Home Bonus\n"
        "  --------------------------------------------------------\n"
        "  Has charger + uses    -0.51      -0.83         +1.07\n"
        "  Has charger, unused   -2.02      -1.05          0.00\n"
        "  NO home charger      -10.46      -7.59         +0.17\n\n"
        "Key Equity Findings\n"
        "  - No-charger agents score 20x worse than home-charger agents\n"
        "  - 69% of <$25K income agents have no home charger\n"
        "  - 85% of renters have no home charger\n"
        "  - 100% of apartment dwellers have no home charger\n"
        "  - 24,717 agents entirely dependent on public infrastructure",
        "4CAF50", False
    ),
    (
        "Research Outputs & Future Studies",
        "",
        "Charging Behavior (Iteration 5)\n"
        "  Public: 16,726 sessions | Home: 8,562 | Work: 8,142\n"
        "  En-route: 5,054 insertions (85% DCFC, 15% L2)\n"
        "  Overnight plug-in rate: 72% (matches NREL 70-75%)\n\n"
        "Potential Studies\n"
        "  1. Charger infrastructure gap analysis\n"
        "  2. Income-stratified charging equity assessment\n"
        "  3. Grid load profiles (24-hr charging demand curves)\n"
        "  4. PHEV vs BEV electrification rates\n"
        "  5. Home charger penetration impact\n"
        "  6. Charger utilization & revenue modeling\n"
        "  7. Range anxiety geography (corridor SoC profiles)\n"
        "  8. Fleet composition impact on infrastructure\n\n"
        "github.com/Tomal121186621/UrbanEV-MATSim-Maryland",
        "2196F3", False
    ),
    (
        "Thank You",
        "github.com/Tomal121186621/UrbanEV-MATSim-Maryland",
        "130,837 EV Agents  |  33 Vehicle Types (BEV + PHEV)\n"
        "9.8M Link Network  |  1,958 Chargers  |  14 Through Stations\n"
        "8 Scoring Components  |  3 Replanning Strategies  |  6 New Features\n\n"
        "Built on MATSim 12.0 + UrbanEV-v2 (TU Munich / Chalmers)",
        "FFFFFF", True
    ),
]

# ── OOXML Template ────────────────────────────────────────────────────────────

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  {slide_overrides}
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

def make_presentation_xml(n_slides):
    slide_refs = "\n    ".join(
        f'<p:sldId id="{256+i}" r:id="rId{i+2}"/>' for i in range(n_slides)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>
    {slide_refs}
  </p:sldIdLst>
  <p:sldSz cx="9144000" cy="5143500" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

def make_pres_rels(n_slides):
    rels = [f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for i in range(n_slides):
        rels.append(f'<Relationship Id="rId{i+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i+1}.xml"/>')
    rels.append(f'<Relationship Id="rId{n_slides+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  ' + '\n  '.join(rels) + '\n</Relationships>'

def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def make_slide_xml(title, subtitle, body, title_color, bg_dark):
    bg_color = "1A1A2E" if bg_dark else "FFFFFF"
    body_color = "B4B4DC" if bg_dark else "373737"
    sub_color = "B4B4DC" if bg_dark else "777777"

    body_runs = ""
    for line in esc(body).split("\n"):
        body_runs += f"""<a:p><a:r><a:rPr lang="en-US" sz="1000" dirty="0"><a:solidFill><a:srgbClr val="{body_color}"/></a:solidFill><a:latin typeface="Consolas"/></a:rPr><a:t>{line}</a:t></a:r></a:p>\n"""

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:cSld>
  <p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg_color}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
  <p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="400000" y="200000"/><a:ext cx="8344000" cy="600000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="2400" b="1" dirty="0"><a:solidFill><a:srgbClr val="{title_color}"/></a:solidFill><a:latin typeface="Calibri"/></a:rPr><a:t>{esc(title)}</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="3" name="Subtitle"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="400000" y="750000"/><a:ext cx="8344000" cy="300000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1100" dirty="0"><a:solidFill><a:srgbClr val="{sub_color}"/></a:solidFill><a:latin typeface="Calibri"/></a:rPr><a:t>{esc(subtitle)}</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="4" name="Body"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="400000" y="1050000"/><a:ext cx="8344000" cy="3900000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"/><a:lstStyle/>{body_runs}</p:txBody>
    </p:sp>
  </p:spTree>
</p:cSld>
</p:sld>"""

SLIDE_MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>"""

SLIDE_LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 type="blank">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld></p:sldLayout>"""

THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="UrbanEV">
<a:themeElements>
<a:clrScheme name="UrbanEV"><a:dk1><a:srgbClr val="1A1A2E"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="373737"/></a:dk2><a:lt2><a:srgbClr val="F5F5F5"/></a:lt2><a:accent1><a:srgbClr val="2196F3"/></a:accent1><a:accent2><a:srgbClr val="4CAF50"/></a:accent2><a:accent3><a:srgbClr val="FF9800"/></a:accent3><a:accent4><a:srgbClr val="E91E63"/></a:accent4><a:accent5><a:srgbClr val="673AB7"/></a:accent5><a:accent6><a:srgbClr val="009688"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>
<a:fontScheme name="UrbanEV"><a:majorFont><a:latin typeface="Calibri"/></a:majorFont><a:minorFont><a:latin typeface="Calibri"/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
</a:themeElements></a:theme>"""

# ── Build PPTX ────────────────────────────────────────────────────────────────

n = len(SLIDES)
slide_overrides = "\n  ".join(
    f'<Override PartName="/ppt/slides/slide{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
    for i in range(n)
)

with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", CONTENT_TYPES.replace("{slide_overrides}", slide_overrides))
    z.writestr("_rels/.rels", RELS)
    z.writestr("ppt/presentation.xml", make_presentation_xml(n))
    z.writestr("ppt/_rels/presentation.xml.rels", make_pres_rels(n))
    z.writestr("ppt/slideMasters/slideMaster1.xml", SLIDE_MASTER)
    z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
        '</Relationships>')
    z.writestr("ppt/slideLayouts/slideLayout1.xml", SLIDE_LAYOUT)
    z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        '</Relationships>')
    z.writestr("ppt/theme/theme1.xml", THEME)

    for i, (title, subtitle, body, title_color, bg_dark) in enumerate(SLIDES):
        z.writestr(f"ppt/slides/slide{i+1}.xml", make_slide_xml(title, subtitle, body, title_color, bg_dark))
        z.writestr(f"ppt/slides/_rels/slide{i+1}.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            '</Relationships>')

print(f"Generated {OUTPUT} with {n} slides")
