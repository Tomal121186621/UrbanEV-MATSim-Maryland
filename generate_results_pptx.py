#!/usr/bin/env python3
"""
Auto-generate results PPTX from simulation log and output files.
Run after each iteration or on-demand.

Usage: python generate_results_pptx.py
"""
import zipfile
import os
import re
import gzip
from collections import defaultdict

LOG_FILE = "full_simulation.log"
SCORE_FILE = "output/maryland_ev_enhanced/maryland_ev_v2.scorestats.txt"
OUTPUT = "UrbanEV_Results.pptx"

def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def parse_log():
    """Extract key metrics from simulation log."""
    data = {
        "iterations_complete": [],
        "soc_persist": [],
        "soc_problems": [],
        "enroute_total": 0,
        "stuck": [],
        "home_sessions": 0,
        "no_charger": 0,
        "charger_full": 0,
        "workplace_info": "",
        "reliability_info": [],
        "scores": [],
    }

    if not os.path.exists(LOG_FILE):
        return data

    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "### ITERATION" in line and "ENDS" in line:
                m = re.search(r"ITERATION (\d+) ENDS", line)
                if m:
                    data["iterations_complete"].append(int(m.group(1)))

            if "SoC persistence (iter" in line:
                m = re.search(r"iter (\d+)\): (\d+) vehicles.*\| (\d+) plugged.*\| (\d+) home.*\| (\d+) no home", line)
                if m:
                    data["soc_persist"].append({
                        "iter": int(m.group(1)),
                        "updated": int(m.group(2)),
                        "plugged": int(m.group(3)),
                        "home_charged": int(m.group(4)),
                        "no_charger": int(m.group(5)),
                    })

            if "replanning has" in line and "SocProblemCollector" in line:
                m = re.search(r"iteration (\d+) replanning has (\d+) affected", line)
                if m:
                    data["soc_problems"].append({
                        "iter": int(m.group(1)),
                        "problems": int(m.group(2)),
                    })

            if "InsertEnRoute: inserted" in line:
                data["enroute_total"] += 1

            if "AT 240:00:00" in line and "lost=" in line:
                m = re.search(r"lost=(\d+)", line)
                if m:
                    data["stuck"].append(int(m.group(1)))

            if "HOME session" in line:
                data["home_sessions"] += 1

            if "No charger found" in line:
                data["no_charger"] += 1

            if "charger FULL" in line:
                data["charger_full"] += 1

            if "Workplace charging:" in line:
                data["workplace_info"] = line.strip().split("INFO ")[-1] if "INFO " in line else line.strip()

            if "ChargerReliability:" in line:
                data["reliability_info"].append(line.strip().split("INFO ")[-1] if "INFO " in line else line.strip())

    # Parse scores
    if os.path.exists(SCORE_FILE):
        with open(SCORE_FILE, "r") as f:
            for line in f:
                if line.startswith("ITERATION"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 5:
                    try:
                        data["scores"].append({
                            "iter": int(parts[0]),
                            "executed": float(parts[1]),
                            "worst": float(parts[2]),
                            "avg": float(parts[3]),
                            "best": float(parts[4]),
                        })
                    except (ValueError, IndexError):
                        pass

    return data

def make_slide(title, subtitle, body, title_color="1A1A2E", bg_dark=False):
    bg_color = "1A1A2E" if bg_dark else "FFFFFF"
    body_color = "B4B4DC" if bg_dark else "373737"
    sub_color = "B4B4DC" if bg_dark else "777777"

    body_runs = ""
    for line in esc(body).split("\n"):
        body_runs += f'<a:p><a:r><a:rPr lang="en-US" sz="900" dirty="0"><a:solidFill><a:srgbClr val="{body_color}"/></a:solidFill><a:latin typeface="Consolas"/></a:rPr><a:t>{line}</a:t></a:r></a:p>\n'

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
      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="400000" y="150000"/><a:ext cx="8344000" cy="500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="2200" b="1" dirty="0"><a:solidFill><a:srgbClr val="{title_color}"/></a:solidFill><a:latin typeface="Calibri"/></a:rPr><a:t>{esc(title)}</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="3" name="Sub"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="400000" y="620000"/><a:ext cx="8344000" cy="250000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1000" dirty="0"><a:solidFill><a:srgbClr val="{sub_color}"/></a:solidFill><a:latin typeface="Calibri"/></a:rPr><a:t>{esc(subtitle)}</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="4" name="Body"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="400000" y="900000"/><a:ext cx="8344000" cy="4000000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"/><a:lstStyle/>{body_runs}</p:txBody>
    </p:sp>
  </p:spTree>
</p:cSld>
</p:sld>"""

def build_slides(data):
    slides = []
    n_iters = len(data["iterations_complete"])
    last_iter = data["iterations_complete"][-1] if data["iterations_complete"] else -1

    # Slide 1: Title
    slides.append(make_slide(
        "UrbanEV-v2 Maryland: Simulation Results",
        f"Auto-generated after iteration {last_iter} | 130,837 EV Agents | 30 Iterations",
        f"Iterations completed: {n_iters}\n"
        f"Total en-route insertions: {data['enroute_total']:,}\n"
        f"Home charging sessions: {data['home_sessions']:,}\n"
        f"No-charger-found errors: {data['no_charger']:,}\n"
        f"Charger-full retries: {data['charger_full']:,}\n\n"
        f"github.com/Tomal121186621/UrbanEV-MATSim-Maryland",
        "FFFFFF", True
    ))

    # Slide 2: Score Convergence
    score_lines = "Iter   Avg Executed   Avg Worst   Avg Average   Avg Best\n"
    score_lines += "-" * 65 + "\n"
    for s in data["scores"]:
        score_lines += f"  {s['iter']:>2}     {s['executed']:>10.3f}   {s['worst']:>10.3f}   {s['avg']:>10.3f}   {s['best']:>10.3f}\n"

    if data["scores"]:
        first_best = data["scores"][0]["best"]
        last_best = data["scores"][-1]["best"]
        trend = "IMPROVING" if last_best > first_best else "DECLINING" if last_best < first_best else "STABLE"
        score_lines += f"\nAvg Best trend: {first_best:.3f} -> {last_best:.3f} ({trend})"

    slides.append(make_slide(
        "Score Convergence",
        "Avg best should stabilize or improve as agents learn charging strategies",
        score_lines,
        "2196F3"
    ))

    # Slide 3: SoC Persistence & Overnight Charging
    persist_lines = "Iter   Vehicles   Plugged In   Plug Rate   Home Charged   No Charger\n"
    persist_lines += "-" * 75 + "\n"
    for p in data["soc_persist"]:
        rate = p["plugged"] / max(p["updated"], 1) * 100
        persist_lines += f"  {p['iter']:>2}    {p['updated']:>7,}    {p['plugged']:>7,}     {rate:>5.1f}%     {p['home_charged']:>7,}     {p['no_charger']:>6,}\n"

    persist_lines += f"\nOvernight charging model (NREL 2023; INL 2015):\n"
    persist_lines += f"  SoC-dependent plug-in probability: <30%=95%, 30-50%=85%, 50-70%=65%, >90%=10%\n"
    persist_lines += f"  Target SoC: Tesla 80/90/100%, Non-Tesla 80/90/100%, PHEV 100%\n"
    persist_lines += f"  L1 max 11 kWh overnight | L2 max 58 kWh overnight"

    slides.append(make_slide(
        "Multi-Day SoC Persistence & Overnight Charging",
        "End-of-day SoC carried to next iteration with realistic overnight recharging",
        persist_lines,
        "4CAF50"
    ))

    # Slide 4: SoC Problems & En-Route Charging
    problem_lines = "Iter   SoC Problems   En-Route Insertions (cumulative)\n"
    problem_lines += "-" * 55 + "\n"
    for p in data["soc_problems"]:
        problem_lines += f"  {p['iter']:>2}      {p['problems']:>7,}\n"

    problem_lines += f"\nTotal en-route insertions: {data['enroute_total']:,}\n"
    problem_lines += f"\nEn-route charging features:\n"
    problem_lines += f"  - DCFC preferred, L2 fallback only when no DCFC on route\n"
    problem_lines += f"  - Dynamic duration from remaining distance x consumption rate\n"
    problem_lines += f"  - Risk-based charger selection:\n"
    problem_lines += f"    risk_averse (16%): earliest 25%, 30% buffer\n"
    problem_lines += f"    moderate (48%): middle 50%, 15% buffer\n"
    problem_lines += f"    risk_neutral (36%): latest 25%, 5% buffer"

    slides.append(make_slide(
        "SoC Problems & En-Route Charging",
        "Agents with depleted batteries get mid-trip DCFC stops inserted",
        problem_lines,
        "673AB7"
    ))

    # Slide 5: Stuck Agents
    stuck_lines = "Iter   Stuck Agents   % of 130,837\n"
    stuck_lines += "-" * 40 + "\n"
    for i, s in enumerate(data["stuck"]):
        pct = s / 130837 * 100
        stuck_lines += f"  {i:>2}         {s:>5}       {pct:.2f}%\n"

    stuck_lines += f"\nTraffic dynamics: queue (fixes kinematic wave short-link gridlock)\n"
    stuck_lines += f"flowCapacityFactor: 1.0 | storageCapacityFactor: 1.0\n"
    stuck_lines += f"stuckTime: 900s | removeStuckVehicles: true"

    slides.append(make_slide(
        "Stuck Agents (Network Performance)",
        "Queue traffic dynamics eliminated the 95% stuck rate from kinematic waves",
        stuck_lines,
        "2196F3"
    ))

    # Slide 6: Infrastructure
    infra_lines = f"Workplace Charging\n  {data['workplace_info']}\n\n"
    infra_lines += f"Charger Reliability (per iteration)\n"
    for r in data["reliability_info"][:5]:
        infra_lines += f"  {r}\n"
    infra_lines += f"\nCharger Errors\n"
    infra_lines += f"  No charger found: {data['no_charger']:,} total across all iterations\n"
    infra_lines += f"  Charger full retries: {data['charger_full']:,}\n"
    infra_lines += f"\nPublic chargers: 1,607 L2 + 283 DCFC + 68 DCFC_TESLA = 1,958 total\n"
    infra_lines += f"Home chargers: 76,787 L2 + 29,333 L1 = 106,120 agents with home charging\n"
    infra_lines += f"Workplace pools: 2,989 shared charger pools (1:5 ratio)"

    slides.append(make_slide(
        "Charging Infrastructure Performance",
        "Workplace competition, charger reliability, and infrastructure gaps",
        infra_lines,
        "FF9800"
    ))

    # Slide 7: Summary
    summary = f"Simulation Progress: {n_iters} of 30 iterations complete\n\n"
    summary += f"Key Metrics (latest iteration):\n"
    if data["scores"]:
        latest = data["scores"][-1]
        summary += f"  Avg executed score: {latest['executed']:.3f}\n"
        summary += f"  Avg best score: {latest['best']:.3f}\n"
    if data["stuck"]:
        summary += f"  Stuck agents: {data['stuck'][-1]} ({data['stuck'][-1]/130837*100:.2f}%)\n"
    if data["soc_problems"]:
        summary += f"  SoC problems: {data['soc_problems'][-1]['problems']:,}\n"
    summary += f"  En-route insertions: {data['enroute_total']:,}\n"
    summary += f"  Home sessions: {data['home_sessions']:,}\n\n"

    summary += f"Features Active:\n"
    summary += f"  [x] PHEV gas fallback (40K PHEV agents)\n"
    summary += f"  [x] Multi-day SoC persistence + overnight charging\n"
    summary += f"  [x] Workplace charger competition (1:5 ratio)\n"
    summary += f"  [x] Cost-aware charging (softmax weighted)\n"
    summary += f"  [x] Charger reliability (80% DCFC, 92% L2)\n"
    summary += f"  [x] Dynamic en-route charging (DCFC preferred)\n"
    summary += f"  [x] Research-backed scoring calibration (8 params)"

    slides.append(make_slide(
        f"Summary — After Iteration {last_iter}",
        "Auto-updated | github.com/Tomal121186621/UrbanEV-MATSim-Maryland",
        summary,
        "4CAF50"
    ))

    return slides

def write_pptx(slides):
    """Write slides to PPTX using raw OOXML."""
    n = len(slides)

    slide_overrides = "\n  ".join(
        f'<Override PartName="/ppt/slides/slide{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(n)
    )

    content_types = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  {slide_overrides}
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>"""

    slide_refs = "\n    ".join(f'<p:sldId id="{256+i}" r:id="rId{i+2}"/>' for i in range(n))
    presentation = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_refs}</p:sldIdLst>
  <p:sldSz cx="9144000" cy="5143500" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

    pres_rels_items = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(n):
        pres_rels_items.append(f'<Relationship Id="rId{i+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i+1}.xml"/>')
    pres_rels_items.append(f'<Relationship Id="rId{n+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>')
    pres_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  ' + '\n  '.join(pres_rels_items) + '\n</Relationships>'

    slide_master = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'
    slide_layout = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" type="blank"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld></p:sldLayout>'
    theme = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Results"><a:themeElements><a:clrScheme name="Results"><a:dk1><a:srgbClr val="1A1A2E"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="373737"/></a:dk2><a:lt2><a:srgbClr val="F5F5F5"/></a:lt2><a:accent1><a:srgbClr val="2196F3"/></a:accent1><a:accent2><a:srgbClr val="4CAF50"/></a:accent2><a:accent3><a:srgbClr val="FF9800"/></a:accent3><a:accent4><a:srgbClr val="E91E63"/></a:accent4><a:accent5><a:srgbClr val="673AB7"/></a:accent5><a:accent6><a:srgbClr val="009688"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Results"><a:majorFont><a:latin typeface="Calibri"/></a:majorFont><a:minorFont><a:latin typeface="Calibri"/></a:minorFont></a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'

    sm_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>'
    sl_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>'
    slide_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'
    root_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>'

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("ppt/presentation.xml", presentation)
        z.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", sm_rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", sl_rels)
        z.writestr("ppt/theme/theme1.xml", theme)
        for i, slide_xml in enumerate(slides):
            z.writestr(f"ppt/slides/slide{i+1}.xml", slide_xml)
            z.writestr(f"ppt/slides/_rels/slide{i+1}.xml.rels", slide_rels)

if __name__ == "__main__":
    print("Parsing simulation data...")
    data = parse_log()
    n = len(data["iterations_complete"])
    print(f"Found {n} completed iterations")

    slides = build_slides(data)
    write_pptx(slides)
    print(f"Generated {OUTPUT} with {len(slides)} slides (after iteration {data['iterations_complete'][-1] if data['iterations_complete'] else 'N/A'})")
