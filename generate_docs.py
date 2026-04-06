#!/usr/bin/env python3
"""
Generate two PDF documents for UrbanEV-v2 project:
  1. prompt_log.pdf      — Serial log of all prompts and results
  2. pipeline_guide.pdf  — Illustrated pipeline overview

Re-run this script to regenerate both PDFs.
"""

from fpdf import FPDF
import textwrap
from datetime import date


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class StyledPDF(FPDF):
    """PDF with consistent headers, footers, and helper methods."""

    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_title = title
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, self.doc_title, align="L")
        self.cell(0, 8, f"Updated: {date.today().isoformat()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, num, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(25, 60, 120)
        self.ln(4)
        self.cell(0, 8, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(25, 60, 120)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def sub_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def code_block(self, text):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(40, 40, 40)
        x0, y0 = self.get_x(), self.get_y()
        # Draw background
        lines = text.strip().split("\n")
        for line in lines:
            # Wrap long lines
            if len(line) > 100:
                line = line[:97] + "..."
            self.cell(190, 4.5, "  " + line, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def bullet(self, text):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.cell(5, 5, "-")
        self.multi_cell(175, 5, text)
        self.ln(1)

    def key_value(self, key, value):
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(60, 60, 60)
        self.cell(55, 5, key)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, str(value))

    def table_row(self, cells, widths, bold=False):
        style = "B" if bold else ""
        self.set_font("Helvetica", style, 8.5)
        h = 5.5
        for i, (cell, w) in enumerate(zip(cells, widths)):
            self.cell(w, h, str(cell), border=1)
        self.ln(h)

    def colored_box(self, text, r, g, b):
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(40, 7, text, fill=True, align="C")
        self.set_text_color(30, 30, 30)


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF 1: PROMPT LOG
# ═══════════════════════════════════════════════════════════════════════════════

def generate_prompt_log():
    pdf = StyledPDF("UrbanEV-v2 Prompt Log", orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()

    # ── Title page ──
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 15, "UrbanEV-v2", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Prompt Log & Session Record", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Last updated: {date.today().isoformat()}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "MATSim EV Simulation for Maryland + DC", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 6,
        "This document records every prompt given to the AI assistant during the "
        "UrbanEV-v2 data preparation pipeline, along with key results and outputs. "
        "It serves as a reproducible audit trail of the entire workflow.",
        align="C")

    # ── Prompt 1 ──
    pdf.add_page()
    pdf.section_title("P1", "Convert AFDC Charger Station CSVs to MATSim chargers.xml")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Convert two AFDC (Alternative Fuels Data Center) CSV exports of EV charger stations "
        "(Maryland and DC) into a single MATSim-compatible chargers.xml file for UrbanEV-v2.")
    pdf.sub_title("Input Files")
    pdf.bullet("alt_fuel_stations (Mar 1 2026)_MD.csv")
    pdf.bullet("alt_fuel_stations (Mar 1 2026)_DC.csv")
    pdf.bullet("maryland-dc-ev-network.xml.gz (for CRS detection)")
    pdf.sub_title("Processing Rules Specified")
    pdf.bullet("Filter: Status=E (existing), public access only, valid lat/lon")
    pdf.bullet("Exclude Tesla Destination chargers (keep Superchargers)")
    pdf.bullet("Separate charger entries per power level (L2 vs DCFC at same station)")
    pdf.bullet("Assign plug_power by network: Tesla SC=150kW, EVgo=100kW, EA=150kW, CP=62.5kW, default=50kW")
    pdf.bullet("DCFC_TESLA type for Tesla-only connector stations")
    pdf.bullet("Transform WGS84 coords to network CRS (EPSG:26985) via pyproj")
    pdf.bullet("ID format: {type}_{state}_{seq}, e.g., dcfc_MD_0001")
    pdf.sub_title("Key Results")
    w = [50, 30]
    pdf.table_row(["Metric", "Value"], w, bold=True)
    pdf.table_row(["Network CRS", "EPSG:26985"], w)
    pdf.table_row(["Total charger entries", "1,958"], w)
    pdf.table_row(["L2 chargers", "1,607"], w)
    pdf.table_row(["DCFC chargers", "283"], w)
    pdf.table_row(["DCFC_TESLA chargers", "68"], w)
    pdf.table_row(["Tesla Dest excluded", "96"], w)
    pdf.sub_title("Output Files")
    pdf.bullet("chargers.xml -- MATSim charger definitions (1,958 entries)")
    pdf.bullet("chargers_metadata.csv -- companion analysis file")
    pdf.bullet("convert_afdc_to_chargers_xml.py -- conversion script")

    # ── Prompt 2 ──
    pdf.add_page()
    pdf.section_title("P2", "Explore Synthetic Population CSV Structure")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Strategically explore the 6.6 GB synthetic population CSV without loading it into memory. "
        "Determine structure, column types, coordinate system, and EV-related fields.")
    pdf.sub_title("Method")
    pdf.bullet("bash head/wc/tail for structure (no pandas load)")
    pdf.bullet("Random 1000-row sample via pandas skiprows for statistics")
    pdf.bullet("Examined dtypes, nulls, value_counts, coordinate ranges")
    pdf.sub_title("Key Findings")
    w = [55, 60]
    pdf.table_row(["Property", "Value"], w, bold=True)
    pdf.table_row(["File size", "6.6 GB (7.1 GB on disk)"], w)
    pdf.table_row(["Total rows", "20,285,076"], w)
    pdf.table_row(["Columns", "63"], w)
    pdf.table_row(["Structure", "One row per TRIP"], w)
    pdf.table_row(["Unique persons", "~6.05 million"], w)
    pdf.table_row(["Max trips/person", "15"], w)
    pdf.table_row(["Coordinate CRS", "EPSG:26985 (matches network)"], w)
    pdf.table_row(["assigned_ev=1 share", "~2.1% of persons"], w)
    pdf.table_row(["has_ev=1 share", "~5.8% of persons"], w)
    pdf.table_row(["Null values", "None (except ev_make/model/body for non-EV)"], w)
    pdf.table_row(["Time format", "Integer HHMM (e.g., 1430 = 14:30)"], w)

    # ── Prompt 3 ──
    pdf.add_page()
    pdf.section_title("P3", "Detailed Column Value Analysis (50K rows)")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Print unique values with counts for 12 key columns using first 50,000 rows. "
        "Determine code meanings for activity types, income, dwelling, employment, travel mode, and fuel type.")
    pdf.sub_title("Initial Guesses vs. Actual (from next prompt with codebook)")
    pdf.body_text(
        "Several initial guesses about code meanings were later corrected when the RTS codebook was provided.")

    # ── Prompt 4 ──
    pdf.section_title("P4", "Apply RTS Codebook to Correct Code Mappings")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Read the official RTS Public File data dictionary (Excel) and revise all code mappings "
        "from the previous analysis.")
    pdf.sub_title("Input")
    pdf.bullet("RTS_Public_File_data_dictionary.xlsx (sheets: Household, Person, Vehicle, Trip)")
    pdf.sub_title("Key Corrections Applied")
    pdf.bullet("o_activity/d_activity: Confirmed from Trip sheet O_ACTIVITY (1=Home through 18=Other)")
    pdf.bullet("hh_income_detailed: Uses MPO 10-bracket version (0-indexed): 0=<$10K ... 9=$200K+")
    pdf.bullet("home_type: Uses MPO_HOME_TYPE codes directly (1=SFD, 2=SFA, 3=2-9apt, 4=10-49apt, 5=50+apt, 6=Mobile)")
    pdf.bullet("home_ownership: MPO codes (1=Own, 2=Rent, 3=Job/military, 4=Family/friend)")
    pdf.bullet("employment_status: RTS codes 0-7 + synthetic additions 8=Child, 9=N/A")
    pdf.bullet("travel_mode: 1=Walk, 2=Bike, 3=Motorcycle, 4=Auto(driver), 5=Auto(passenger), 6=SchoolBus, 7=Rail, 8=Bus, etc.")
    pdf.bullet("CRITICAL: is_car_trip=1 includes Walk/Bike/Motorcycle -- true car-driver = travel_mode==4 only")
    pdf.bullet("fueltype: Custom synthetic encoding (0=N/A, 1=Gas, 2=Diesel, 3=PHEV, 4=BEV, 5=HEV) -- differs from codebook order")
    pdf.bullet("gender: 1=Female, 2=Male (codebook); 0 and 3 added during synthesis")

    # ── Prompt 5 ──
    pdf.add_page()
    pdf.section_title("P5", "Convert Synthetic Population to MATSim Input Files")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Stream the 6.6 GB CSV and generate four MATSim input files for the ~125K EV agents. "
        "Never load the full file into memory.")
    pdf.sub_title("Processing Approach")
    pdf.bullet("Single-pass streaming via csv.DictReader (file sorted by person_id)")
    pdf.bullet("Accumulate trips per person, flush to XML on person boundary")
    pdf.bullet("Only process assigned_ev=1 persons")
    pdf.bullet("Derive charging behavior attributes from demographics")
    pdf.sub_title("Derived Attributes")
    pdf.bullet("homeChargerPower: Based on home_type + ownership + income (0, 1.4, or 7.2 kW)")
    pdf.bullet("workChargerPower: 7.2 kW if charge_at_work_dummy=1, else 0")
    pdf.bullet("rangeAnxietyThreshold: SoC fraction 0.1-0.4, varies by income and age")
    pdf.bullet("betaMoney: Marginal utility of money, VOT-anchored by income")
    pdf.bullet("riskAttitude: risk_neutral / moderate / risk_averse")
    pdf.bullet("smartChargingAware: Boolean, probability based on income + age")
    pdf.bullet("valueOfTime: $/hr based on 50% of hourly wage, reduced for non-workers")
    pdf.sub_title("Output Files (v1 -- before external trip handling)")
    w = [55, 25, 40]
    pdf.table_row(["File", "Size", "Contents"], w, bold=True)
    pdf.table_row(["plans_maryland_ev.xml.gz", "11.8 MB", "114,753 persons"], w)
    pdf.table_row(["electric_vehicles.xml", "13.4 MB", "114,753 vehicles"], w)
    pdf.table_row(["vehicletypes.xml", "20.4 KB", "35 vehicle types"], w)
    pdf.table_row(["ev_population_summary.csv", "15.9 MB", "114,753 rows"], w)
    pdf.sub_title("Issue Identified")
    pdf.body_text(
        "7,728 trips skipped due to (0,0) coordinates -- these are external trips going outside "
        "the MD+DC study area. 1,481 persons lost entirely because all their trips were external.")

    # ── Prompt 6 ──
    pdf.add_page()
    pdf.section_title("P6", "Handle External Trips via Through Stations")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Classify trips as I-I, I-E, E-I, or E-E using FIPS codes. Identify highway boundary "
        "crossing points (through stations) on the MATSim network. Assign through-station "
        "coordinates to external trip ends. Re-run the full conversion.")
    pdf.sub_title("Step 1: Trip Classification (from 100K row sample)")
    w = [25, 30]
    pdf.table_row(["Class", "Share"], w, bold=True)
    pdf.table_row(["I-I", "96.1%"], w)
    pdf.table_row(["I-E", "1.8%"], w)
    pdf.table_row(["E-I", "1.8%"], w)
    pdf.table_row(["E-E", "0.4%"], w)
    pdf.body_text("Virginia (FIPS 51) dominates external trips, especially Fairfax County (51059).")

    pdf.sub_title("Step 2: Through Station Identification")
    pdf.body_text(
        "Network has 4.9M nodes, 9.8M links, zero degree-1 dead ends (fully connected OSM network). "
        "Used manual approach: defined 14 known highway border crossing points, projected to EPSG:26985, "
        "and snapped to nearest network node (max snap distance 234m).")
    pdf.sub_title("14 Through Stations Created")
    w2 = [30, 30, 30]
    pdf.table_row(["Station", "Highway", "Target"], w2, bold=True)
    pdf.table_row(["TS_I95_N", "I-95", "PA,NJ,NY"], w2)
    pdf.table_row(["TS_I95_S", "I-95/I-495", "VA"], w2)
    pdf.table_row(["TS_I70_W", "I-70", "WV"], w2)
    pdf.table_row(["TS_I68_W", "I-68", "WV"], w2)
    pdf.table_row(["TS_I81_S", "I-81", "WV,VA"], w2)
    pdf.table_row(["TS_I270_S", "I-270/I-495", "VA"], w2)
    pdf.table_row(["TS_US50_E", "US-50", "DE"], w2)
    pdf.table_row(["TS_US301_N", "US-301", "DE,PA,NJ"], w2)
    pdf.table_row(["TS_US13_N", "US-40/US-13", "DE,PA"], w2)
    pdf.table_row(["TS_DC_NW", "I-495/I-270", "DC"], w2)
    pdf.table_row(["TS_DC_NE", "US-50/I-495", "DC"], w2)
    pdf.table_row(["TS_RT1_S", "US-1/I-295", "VA"], w2)
    pdf.table_row(["TS_US15_N", "US-15", "PA"], w2)
    pdf.table_row(["TS_I83_N", "I-83", "PA"], w2)

    pdf.sub_title("Step 3-4: Updated Conversion Results")
    w3 = [55, 30, 30]
    pdf.table_row(["Metric", "Before", "After"], w3, bold=True)
    pdf.table_row(["EV persons written", "114,753", "116,234"], w3)
    pdf.table_row(["EV trips written", "374,533", "382,261"], w3)
    pdf.table_row(["Trips skipped", "7,728", "0"], w3)
    pdf.table_row(["Warnings", "1,481", "0"], w3)
    pdf.ln(3)
    pdf.body_text(
        "All 7,728 previously-skipped trips recovered. 3,399 persons (2.9%) flagged with "
        "hasExternalTrips=true for corridor range anxiety analysis. "
        "Most-used stations: TS_US301_N (1,945), TS_I83_N (1,256), TS_DC_NE (1,026).")

    # -- Prompt 7 --
    pdf.add_page()
    pdf.section_title("P7", "Generate MATSim config.xml")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Generate a complete MATSim config.xml for running UrbanEV-v2 on the Maryland+DC "
        "study area with all enhanced framework parameters.")
    pdf.sub_title("Configuration Summary")
    w = [55, 55]
    pdf.table_row(["Parameter", "Value"], w, bold=True)
    pdf.table_row(["Modules", "13"], w)
    pdf.table_row(["Iterations", "60"], w)
    pdf.table_row(["flowCapacityFactor", "0.02"], w)
    pdf.table_row(["storageCapacityFactor", "0.06"], w)
    pdf.table_row(["QSim endTime", "168:00:00 (7-day)"], w)
    pdf.table_row(["Activity types", "14"], w)
    pdf.table_row(["urban_ev params", "38"], w)
    pdf.table_row(["CRS", "EPSG:26985"], w)
    pdf.table_row(["Output dir", "output/maryland_ev_enhanced/"], w)
    pdf.sub_title("Activity Types (14)")
    pdf.body_text(
        "Standard: home, work, school, other. "
        "Charging: home/work/school/other charging. "
        "Charging failed: home/work/school/other charging failed. "
        "Interaction: car interaction, pt interaction.")
    pdf.sub_title("Strategy (2 subpopulations)")
    pdf.bullet("nonCriticalSOC: SelectExpBeta(0.6) + ChangeChargingBehaviour(0.2) + InsertEnRouteCharging(0.2)")
    pdf.bullet("criticalSOC: ChangeChargingBehaviour(0.4) + InsertEnRouteCharging(0.6)")
    pdf.sub_title("Pricing (Maryland rates, USD/kWh)")
    w2 = [40, 25]
    pdf.table_row(["Tier", "Cost"], w2, bold=True)
    pdf.table_row(["Home", "$0.13"], w2)
    pdf.table_row(["Work", "$0.00"], w2)
    pdf.table_row(["Public L1", "$0.18"], w2)
    pdf.table_row(["Public L2", "$0.25"], w2)
    pdf.table_row(["Public DCFC", "$0.48"], w2)
    pdf.sub_title("Output")
    pdf.bullet("scenarios/maryland/config.xml -- Complete MATSim configuration (13 modules)")

    # -- Prompt 8 --
    pdf.add_page()
    pdf.section_title("P8", "Create CLAUDE.md and Documentation PDFs")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Create project CLAUDE.md for AI assistant context, prompt_log.pdf for prompt audit trail, "
        "and pipeline_guide.pdf for pipeline illustration. All kept in project root and updated "
        "after each task.")
    pdf.sub_title("Files Created")
    pdf.bullet("CLAUDE.md -- Project reference with directory structure, data facts, code mappings, "
               "derived attribute rules, config summary, conventions, and known limitations")
    pdf.bullet("prompt_log.pdf -- Serial log of all prompts P1-P8 with results")
    pdf.bullet("pipeline_guide.pdf -- Illustrated pipeline overview")
    pdf.bullet("generate_docs.py -- PDF generator script (re-run to update)")

    # -- Prompt 9 --
    pdf.add_page()
    pdf.section_title("P9", "Full UrbanEV-v2 Java Codebase Review")
    pdf.sub_title("Objective")
    pdf.body_text(
        "Read all 85 Java files across 7 packages. Map class dependencies, event flows, "
        "Guice bindings, and config parameter gaps. No code modifications -- analysis only.")
    pdf.sub_title("Codebase Summary")
    w = [40, 50]
    pdf.table_row(["Metric", "Value"], w, bold=True)
    pdf.table_row(["Java files", "85"], w)
    pdf.table_row(["Packages", "7 (got, urbanEV, charging, config, discharging, fleet, infrastructure, planning, scoring, stats)"], w)
    pdf.table_row(["MATSim version", "12.0"], w)
    pdf.table_row(["Java version", "11"], w)
    pdf.table_row(["Entry point", "se.got.GotEVMain"], w)
    pdf.sub_title("Config Gap: 15 Missing Parameters")
    pdf.body_text(
        "15 params in our config.xml have no matching @StringGetter/@StringSetter in Java: "
        "usePersonLevelParams, publicL1Cost, publicL2Cost, publicDCFCCost, l2PowerThreshold, "
        "dcfcPowerThreshold, baseValueOfTimeFactor, queueAnnoyanceFactor, detourDisutilityPerHour, "
        "enableEnRouteCharging, enRouteSearchRadius, enRouteSafetyBuffer, socProblemThreshold, "
        "chargersFile, electricVehiclesFile. The last 2 belong in EvConfigGroup (moved in config fix).")
    pdf.sub_title("Critical Finding: Charger Type Mismatch")
    pdf.body_text(
        "Our chargers.xml uses types L2/DCFC/DCFC_TESLA. Our electric_vehicles.xml uses "
        "charger_types='default'. findBestCharger() checks ev.getChargerTypes().contains(charger.getType()) "
        "-- these won't match. Must fix vehicle charger_types or add compatibility mapping.")
    pdf.sub_title("Files to Modify (7)")
    pdf.bullet("UrbanEVConfigGroup.java -- add 13 new config params + getters/setters")
    pdf.bullet("ChargingBehaviourScoringParameters.java -- add new fields + Builder")
    pdf.bullet("ChargingBehaviourScoring.java -- 3-tier pricing, person-level betaMoney, VoT")
    pdf.bullet("VehicleChargingHandler.java -- pass charger power to scoring event")
    pdf.bullet("ChargingBehaviourScoringEvent.java -- add chargerPowerKw field")
    pdf.bullet("GotEVMain.java -- en-route strategy, subpop switching")
    pdf.bullet("MobsimScopeEventHandling.java -- person-level params, subpop logic")
    pdf.sub_title("Files to Create (2)")
    pdf.bullet("InsertEnRouteCharging.java -- new PlanStrategy for en-route charging")
    pdf.bullet("InsertEnRouteChargingModule.java -- Guice Provider for the strategy")
    pdf.sub_title("Output")
    pdf.bullet("CODEBASE_ANALYSIS.md -- complete architecture document in project root")

    # -- Prompt 10 --
    pdf.add_page()
    pdf.section_title("P10", "Fix Charger Type Compatibility Mismatch")
    pdf.sub_title("Problem")
    pdf.body_text(
        "electric_vehicles.xml had charger_types='default' but chargers.xml uses L2/DCFC/DCFC_TESLA. "
        "findBestCharger() checks ev.getChargerTypes().contains(charger.getChargerType()) -- no match.")
    pdf.sub_title("Fix Applied")
    pdf.bullet("Tesla vehicles (60,217): charger_types='L1,L2,DCFC,DCFC_TESLA'")
    pdf.bullet("Non-Tesla vehicles (56,017): charger_types='L1,L2,DCFC'")
    pdf.bullet("L1 included for home chargers at 1.4 kW generated by MobsimScopeEventHandling")
    pdf.sub_title("Remaining Java Fix Required")
    pdf.body_text(
        "MobsimScopeEventHandling.addPrivateCharger() creates private home/work chargers with "
        "DEFAULT_CHARGER_TYPE='default'. Must change to derive type from power: "
        "power >= 3kW -> 'L2', power < 3kW -> 'L1'. Documented in CODEBASE_ANALYSIS.md.")

    # -- Prompt 11 --
    pdf.add_page()
    pdf.section_title("P11", "Verify & Correct EV Specifications with Citations")
    pdf.sub_title("Problem")
    pdf.body_text(
        "Battery capacity and consumption values in convert_synpop_to_matsim.py were from "
        "AI training knowledge without citations. User requested verification against "
        "authoritative sources and a cited reference PDF.")
    pdf.sub_title("Method")
    pdf.bullet("Fetched all 592 EVs from EPA fueleconomy.gov (6 pages, kWh/100mi ratings)")
    pdf.bullet("Fetched battery specs from Wikipedia vehicle articles (usable kWh from OEM data)")
    pdf.bullet("Cross-referenced with ev-database.org usable capacity cheatsheet")
    pdf.sub_title("Key Corrections (18 battery values)")
    pdf.bullet("Model Y: 75->81 kWh (was SR value, should be LR AWD)")
    pdf.bullet("Model 3: 60->78 kWh (was old/SR, should be Highland LR)")
    pdf.bullet("F-150 Lightning: 98->131 kWh (was SR, should be Extended Range)")
    pdf.bullet("Mustang Mach-E: 72->88 kWh (was SR, should be ER usable)")
    pdf.bullet("BMW iX: 77->105 kWh (was xDrive40, should be xDrive50)")
    pdf.bullet("Taycan: 93->84 kWh (was gross PB+, should be usable)")
    pdf.bullet("+ 12 minor corrections (gross->usable adjustments)")
    pdf.sub_title("Consumption values also corrected to match EPA kWh/100mi exactly")
    pdf.sub_title("Output")
    pdf.bullet("ev_specifications_reference.pdf -- 4-page reference with all 38 models, sources, color-coded")
    pdf.bullet("convert_synpop_to_matsim.py updated and re-run")
    pdf.bullet("All output files regenerated (electric_vehicles.xml, vehicletypes.xml, etc.)")

    # Save
    pdf.output("/Users/tomal/Documents/URBAN EV Version 2_Reframed/prompt_log.pdf")
    print("Written: prompt_log.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF 2: PIPELINE GUIDE
# ════════════════════════════════════════════════════════════════════════════���══

def generate_pipeline_guide():
    pdf = StyledPDF("UrbanEV-v2 Pipeline Guide", orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()

    # ── Title page ──
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 15, "UrbanEV-v2", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Data Preparation Pipeline", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Last updated: {date.today().isoformat()}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "MATSim EV Simulation for Maryland + DC", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Pipeline Overview ──
    pdf.add_page()
    pdf.section_title("1", "Pipeline Overview")
    pdf.body_text(
        "The UrbanEV-v2 data preparation pipeline converts raw input data (charger station CSVs, "
        "synthetic population, road network) into MATSim-compatible XML files for electric vehicle "
        "simulation over the Maryland + DC study area.")
    pdf.ln(2)

    # Draw pipeline flowchart
    pdf.set_font("Helvetica", "B", 10)
    y = pdf.get_y()
    box_w, box_h = 55, 14
    arrow_gap = 6

    def draw_box(x, y, text, r, g, b):
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, y)
        pdf.cell(box_w, box_h, text, fill=True, align="C")
        return y + box_h

    def draw_arrow(x, y1, y2):
        mid = x + box_w / 2
        pdf.set_draw_color(100, 100, 100)
        pdf.line(mid, y1, mid, y2)
        # arrowhead
        pdf.line(mid - 2, y2 - 3, mid, y2)
        pdf.line(mid + 2, y2 - 3, mid, y2)

    # Column 1: Inputs
    col1_x = 12
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(col1_x, y)
    pdf.cell(box_w, 6, "RAW INPUTS", align="C", new_x="LMARGIN", new_y="NEXT")
    y_start = y + 8
    y1 = draw_box(col1_x, y_start, "AFDC CSVs", 70, 130, 180)
    y1 = draw_box(col1_x, y1 + 3, "MD+DC", 70, 130, 180)
    y2 = draw_box(col1_x, y1 + 8, "Synth Pop CSV", 70, 130, 180)
    y2 = draw_box(col1_x, y2 + 3, "6.6 GB", 70, 130, 180)
    y3 = draw_box(col1_x, y2 + 8, "MATSim Network", 70, 130, 180)
    y3 = draw_box(col1_x, y3 + 3, ".xml.gz", 70, 130, 180)

    # Column 2: Processing
    col2_x = 77
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(col2_x, y)
    pdf.cell(box_w, 6, "PROCESSING", align="C", new_x="LMARGIN", new_y="NEXT")
    py1 = draw_box(col2_x, y_start + 4, "Charger Converter", 180, 100, 50)
    draw_arrow(col1_x + box_w + 3, y_start + box_h / 2 + 4, y_start + box_h / 2 + 4)  # horiz
    pdf.line(col1_x + box_w, y_start + box_h / 2 + 4, col2_x, y_start + box_h / 2 + 4)

    py2 = draw_box(col2_x, py1 + 12, "Synth Pop Converter", 180, 100, 50)
    pdf.line(col1_x + box_w, y1 + 12 + box_h / 2, col2_x, py1 + 12 + box_h / 2)

    py3 = draw_box(col2_x, py2 + 12, "Through Station", 180, 100, 50)
    py3b = draw_box(col2_x, py3 + 3, "Assignment", 180, 100, 50)

    # Column 3: Outputs
    col3_x = 142
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(col3_x, y)
    pdf.cell(box_w, 6, "MATSIM OUTPUTS", align="C", new_x="LMARGIN", new_y="NEXT")
    oy1 = draw_box(col3_x, y_start, "chargers.xml", 50, 150, 80)
    pdf.line(col2_x + box_w, y_start + box_h / 2 + 4, col3_x, y_start + box_h / 2)
    oy2 = draw_box(col3_x, oy1 + 6, "plans.xml.gz", 50, 150, 80)
    pdf.line(col2_x + box_w, py1 + 12 + box_h / 2, col3_x, oy1 + 6 + box_h / 2)
    oy3 = draw_box(col3_x, oy2 + 6, "electric_vehicles", 50, 150, 80)
    oy3b = draw_box(col3_x, oy3 + 3, ".xml", 50, 150, 80)
    oy4 = draw_box(col3_x, oy3b + 6, "vehicletypes.xml", 50, 150, 80)
    oy5 = draw_box(col3_x, oy4 + 6, "through_stations", 50, 150, 80)
    oy5b = draw_box(col3_x, oy5 + 3, ".csv", 50, 150, 80)

    # ── Stage 1 detail ──
    pdf.set_y(oy5b + 20)
    pdf.section_title("2", "Stage 1: Charger Station Conversion")
    pdf.sub_title("Script: convert_afdc_to_chargers_xml.py")
    pdf.body_text(
        "Reads AFDC CSV exports for Maryland and DC. Filters for public, existing EV stations. "
        "Creates separate charger entries for L2 and DCFC at each station. Transforms WGS84 "
        "coordinates to EPSG:26985 (Maryland State Plane). Assigns power ratings by charging network.")
    pdf.ln(1)
    w = [45, 20, 15, 25]
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.table_row(["Filter", "MD", "DC", "Total"], w, bold=True)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.table_row(["Input stations", "1,718", "321", "2,039"], w)
    pdf.table_row(["Not ELEC", "-69", "0", "-69"], w)
    pdf.table_row(["Tesla Destination", "-56", "-40", "-96"], w)
    pdf.table_row(["Final charger entries", "1,676", "282", "1,958"], w)

    # ── Stage 2 detail ──
    pdf.add_page()
    pdf.section_title("3", "Stage 2: Synthetic Population Conversion")
    pdf.sub_title("Script: convert_synpop_to_matsim.py")
    pdf.body_text(
        "Streams the 6.6 GB CSV in a single pass using csv.DictReader. The file is sorted by "
        "person_id, so trips are accumulated per person and flushed to XML when a new person_id "
        "is encountered. Only assigned_ev=1 persons (~116K) are processed.")
    pdf.sub_title("Data Flow")
    pdf.bullet("Read CSV row by row (never load full file)")
    pdf.bullet("Skip non-EV persons immediately (don't parse coords)")
    pdf.bullet("Accumulate trips per person, sorted by tripno")
    pdf.bullet("Classify trips as I-I / I-E / E-I / E-E via FIPS codes")
    pdf.bullet("For external trips: substitute through-station coordinates")
    pdf.bullet("Derive charging behavior attributes from demographics")
    pdf.bullet("Write person + plan to gzipped XML stream")
    pdf.bullet("Collect EV vehicle records for electric_vehicles.xml")

    pdf.sub_title("Activity Code Mapping (RTS Codebook)")
    w2 = [15, 45, 30]
    pdf.table_row(["Code", "RTS Label", "MATSim Type"], w2, bold=True)
    pdf.table_row(["1", "Home", "home"], w2)
    pdf.table_row(["2", "Work", "work"], w2)
    pdf.table_row(["4", "School", "school"], w2)
    pdf.table_row(["3,5-18", "Volunteer/Shop/Meal/etc.", "other"], w2)

    pdf.sub_title("Travel Mode Mapping")
    w3 = [15, 45, 30]
    pdf.table_row(["Code", "RTS Label", "MATSim Mode"], w3, bold=True)
    pdf.table_row(["4", "Auto (driver)", "car"], w3)
    pdf.table_row(["1-3,5-15", "All others", "walk (teleported)"], w3)

    pdf.sub_title("Derived Attribute Rules")
    pdf.set_font("Courier", "", 7.5)
    pdf.set_fill_color(245, 245, 245)
    rules = [
        "homeChargerPower:",
        "  SFD + own + income>=6($75K+):     7.2 kW",
        "  SFD + own + income 4-5($35-75K):  60% -> 7.2, 40% -> 1.4 kW",
        "  SFD + own + income<4(<$35K):       1.4 kW",
        "  SFD + rent + income>=5:            1.4 kW",
        "  SFA + own + income>=5:             1.4 kW",
        "  Apartments (3-5):                  0.0 kW",
        "  Mobile + own:                      1.4 kW",
        "",
        "workChargerPower:  7.2 if charge_at_work_dummy=1, else 0",
        "",
        "betaMoney:  -6.0 * (62500 / income_midpoint)",
        "valueOfTime: (income / 2080) * 0.5 * [0.6 if non-worker]",
    ]
    for line in rules:
        pdf.cell(190, 4, "  " + line, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── Stage 3 detail ──
    pdf.section_title("4", "Stage 3: External Trip Handling")
    pdf.sub_title("Through Station Network")
    pdf.body_text(
        "14 highway boundary crossing points defined at MD state line. Each snapped to nearest "
        "network node (max 234m). Mapped to target state FIPS codes. Stored in through_stations.csv.")
    pdf.sub_title("Assignment Logic")
    pdf.bullet("I-E trip (dest outside, d_x=0): Find station serving dest state FIPS, closest to origin")
    pdf.bullet("E-I trip (origin outside, o_x=0): Find station serving origin state FIPS, closest to dest")
    pdf.bullet("E-E trip (both outside): Assign entry station by origin FIPS, exit by dest FIPS")
    pdf.bullet("Result: 7,728 trips recovered, 0 remaining skips, 1,481 persons re-included")

    # Stage 4: MATSim config
    pdf.add_page()
    pdf.section_title("5", "Stage 4: MATSim Configuration")
    pdf.sub_title("File: scenarios/maryland/config.xml")
    pdf.body_text(
        "Complete MATSim config with 13 modules and 38 urban_ev parameters. "
        "Configured for EV-only simulation (2% sample of full population).")
    pdf.sub_title("Key Simulation Parameters")
    w_cfg = [55, 40]
    pdf.table_row(["Parameter", "Value"], w_cfg, bold=True)
    pdf.table_row(["Iterations", "60"], w_cfg)
    pdf.table_row(["flowCapacityFactor", "0.02"], w_cfg)
    pdf.table_row(["storageCapacityFactor", "0.06"], w_cfg)
    pdf.table_row(["QSim endTime", "168:00:00 (7 days)"], w_cfg)
    pdf.table_row(["Innovation cutoff", "80% of iterations"], w_cfg)
    pdf.table_row(["Plan memory", "5 plans/agent"], w_cfg)
    pdf.sub_title("Scoring: 14 Activity Types")
    pdf.bullet("Standard: home (12h), work (8h), school (6h), other (1.5h)")
    pdf.bullet("Charging: home/work/school/other charging (duration varies)")
    pdf.bullet("Failed: home/work/school/other charging failed (1min penalty)")
    pdf.bullet("Interaction: car interaction, pt interaction (not scored)")
    pdf.sub_title("Strategy: 2 Subpopulations")
    pdf.bullet("nonCriticalSOC: SelectExpBeta 60% + ChangeCharging 20% + EnRoute 20%")
    pdf.bullet("criticalSOC: ChangeCharging 40% + EnRoute 60% (no exploitation)")
    pdf.sub_title("Pricing (Maryland USD/kWh)")
    pdf.body_text("Home: $0.13 | Work: free | L2: $0.25 | DCFC: $0.48")

    # Final outputs
    pdf.add_page()
    pdf.section_title("6", "Final Output Summary")
    w4 = [60, 25, 45]
    pdf.table_row(["File", "Size", "Description"], w4, bold=True)
    pdf.table_row(["chargers.xml", "~200 KB", "1,958 charger locations"], w4)
    pdf.table_row(["chargers_metadata.csv", "~300 KB", "Charger details for analysis"], w4)
    pdf.table_row(["plans_maryland_ev.xml.gz", "12.1 MB", "116,234 EV agent plans"], w4)
    pdf.table_row(["electric_vehicles.xml", "13.6 MB", "116,234 EV definitions"], w4)
    pdf.table_row(["vehicletypes.xml", "20.4 KB", "35 vehicle type specs"], w4)
    pdf.table_row(["through_stations.csv", "~2 KB", "14 boundary crossing points"], w4)
    pdf.table_row(["ev_population_summary.csv", "16.8 MB", "Per-agent attribute summary"], w4)
    pdf.table_row(["config.xml", "~12 KB", "MATSim config (13 modules)"], w4)

    pdf.ln(5)
    pdf.sub_title("EV Agent Population Profile")
    w5 = [55, 30]
    pdf.table_row(["Metric", "Value"], w5, bold=True)
    pdf.table_row(["Total EV agents", "116,234"], w5)
    pdf.table_row(["Total trips", "382,261"], w5)
    pdf.table_row(["Agents with external trips", "3,399 (2.9%)"], w5)
    pdf.table_row(["Top EV: Tesla Model Y", "33,203 (28.6%)"], w5)
    pdf.table_row(["Home L2 charger access", "40,830 (35.1%)"], w5)
    pdf.table_row(["No home charger", "36,341 (31.3%)"], w5)
    pdf.table_row(["Work charger access", "~6.6%"], w5)

    pdf.ln(5)
    pdf.sub_title("Scripts (in Input Files/)")
    pdf.bullet("convert_afdc_to_chargers_xml.py -- AFDC CSV to chargers.xml")
    pdf.bullet("convert_synpop_to_matsim.py -- Synth pop CSV to all MATSim XML files")
    pdf.bullet("generate_docs.py -- This documentation generator (re-run to update)")

    # ── CRS reference ──
    pdf.ln(3)
    pdf.sub_title("Coordinate Reference System")
    pdf.body_text(
        "All spatial data uses EPSG:26985 (NAD83 / Maryland State Plane). "
        "The MATSim network, charger locations, and agent coordinates are all in this CRS. "
        "AFDC charger data (WGS84) was transformed via pyproj during conversion.")

    pdf.output("/Users/tomal/Documents/URBAN EV Version 2_Reframed/pipeline_guide.pdf")
    print("Written: pipeline_guide.pdf")


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    generate_prompt_log()
    generate_pipeline_guide()
    print("\nBoth PDFs generated in project root.")
