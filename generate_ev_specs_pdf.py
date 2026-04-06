#!/usr/bin/env python3
"""
Generate EV Vehicle Specifications Reference PDF with verified data and citations.
"""

from fpdf import FPDF
from datetime import date

# ═══════════════════════════════════════════════════════════════════════════════
#  VERIFIED EV SPECIFICATIONS
#  Sources: EPA fueleconomy.gov (kWh/100mi), Wikipedia (battery kWh, sourced
#  from manufacturer specs and EPA filings), ev-database.org (usable capacity)
# ═══════════════════════════════════════════════════════════════════════════════

# Each entry: (model, make, trim_note,
#   verified_battery_kWh, our_battery_kWh, battery_source,
#   epa_kwh_per_100mi, our_kwh_per_km, consumption_source,
#   verdict_battery, verdict_consumption)

SPECS = [
    # ── Tesla ──────────────────────────────────────────────────────────────
    ("Model Y", "Tesla", "Long Range AWD",
     81, 75, "Wikipedia: Tesla Model Y (81 kWh usable, LR AWD)",
     29, 0.161, "EPA fueleconomy.gov 2024-2025: 27-29 kWh/100mi",
     "LOW (-7%)", "OK"),
    ("Model 3", "Tesla", "Long Range AWD (Highland)",
     78, 60, "Wikipedia: Tesla Model 3 (78.1 kWh usable, LR)",
     26, 0.147, "EPA fueleconomy.gov 2025: 25-26 kWh/100mi",
     "LOW (-23%)", "OK (close to RWD 25)"),
    ("Model S", "Tesla", "Long Range / Plaid",
     95, 100, "Wikipedia: Tesla Model S (95 kWh usable)",
     28, 0.190, "EPA fueleconomy.gov 2024: 28-31 kWh/100mi",
     "CLOSE (+5%)", "OK (28=0.174)"),
    ("Model X", "Tesla", "Long Range / Plaid",
     95, 100, "Wikipedia: Tesla Model X (same pack as Model S)",
     34, 0.200, "EPA fueleconomy.gov 2024: 34-35 kWh/100mi",
     "CLOSE (+5%)", "OK (34=0.211)"),
    ("Cybertruck", "Tesla", "All variants",
     123, 123, "Wikipedia: Tesla Cybertruck (123 kWh)",
     41, 0.250, "EPA fueleconomy.gov 2025: 41-43 kWh/100mi",
     "CORRECT", "OK (41=0.255)"),

    # ── Ford ───────────────────────────────────────────────────────────────
    ("F-150 Lightning", "Ford", "Extended Range",
     131, 98, "Wikipedia: Ford F-150 Lightning (131 kWh ER, 98 kWh SR)",
     48, 0.280, "EPA fueleconomy.gov 2024: 47-51 kWh/100mi",
     "SR ONLY", "OK (48=0.298)"),
    ("Mustang Mach-E", "Ford", "Extended Range",
     88, 72, "Wikipedia: Ford Mustang Mach-E (88 kWh usable ER, 70-72.6 SR)",
     32, 0.195, "EPA fueleconomy.gov 2025: 31-34 kWh/100mi",
     "SR ONLY", "OK (32=0.199)"),

    # ── Chevrolet / GM ─────────────────────────────────────────────────────
    ("Bolt EV", "Chevrolet", "2020-2023",
     66, 65, "Wikipedia: Chevrolet Bolt (66 kWh, 2020+)",
     29, 0.170, "EPA fueleconomy.gov: ~29 kWh/100mi",
     "CLOSE (-2%)", "OK (29=0.180)"),
    ("Bolt EUV", "Chevrolet", "2022-2023",
     66, 65, "Wikipedia: same platform as Bolt EV (66 kWh)",
     29, 0.175, "EPA fueleconomy.gov: ~29 kWh/100mi",
     "CLOSE (-2%)", "OK"),
    ("Equinox EV", "Chevrolet", "FWD",
     85, 85, "Honda Prologue wiki (shared Ultium, 85 kWh)",
     31, 0.190, "EPA fueleconomy.gov 2025: 31-35 kWh/100mi",
     "CORRECT", "OK (31=0.193)"),
    ("Blazer EV", "Chevrolet", "FWD / AWD",
     85, 85, "GM Ultium platform (same as Equinox EV pack option)",
     32, 0.200, "EPA fueleconomy.gov 2025: 32-35 kWh/100mi",
     "CORRECT", "OK (32=0.199)"),
    ("Silverado EV", "Chevrolet", "Max Range / WT",
     205, 200, "Wikipedia: Chevrolet Silverado EV (205 kWh max range)",
     48, 0.300, "EPA fueleconomy.gov 2024-2025: 48-53 kWh/100mi",
     "CLOSE (-2%)", "OK (48=0.298)"),

    # ── Cadillac / GMC / Rivian ────────────────────────────────────────────
    ("Lyriq", "Cadillac", "AWD",
     100, 102, "Wikipedia: Cadillac Lyriq (100 kWh usable, 102 gross)",
     40, 0.210, "EPA fueleconomy.gov 2025: 40 kWh/100mi",
     "GROSS used", "OK (40=0.249, HIGH)"),
    ("Hummer EV", "GMC", "Pickup / SUV",
     213, 213, "Wikipedia: GMC Hummer EV (212.7 kWh usable)",
     63, 0.330, "EPA fueleconomy.gov 2024: 63-72 kWh/100mi",
     "CORRECT", "OK (63=0.391, LOW)"),
    ("R1S", "Rivian", "Large Pack",
     135, 135, "Wikipedia: Rivian R1S (135 kWh Large pack)",
     41, 0.235, "EPA fueleconomy.gov 2024-2025: 39-45 kWh/100mi",
     "CORRECT", "OK (41=0.255)"),
    ("R1T", "Rivian", "Large Pack",
     135, 135, "Wikipedia: Rivian R1T (135 kWh Large pack)",
     41, 0.240, "EPA fueleconomy.gov 2024-2025: 39-45 kWh/100mi",
     "CORRECT", "OK"),

    # ── Nissan ─────────────────────────────────────────────────────────────
    ("Leaf", "Nissan", "S/SV (2024, Gen 2)",
     39, 40, "Wikipedia: Nissan Leaf (39 kWh usable, 40 gross Gen 2)",
     30, 0.175, "EPA fueleconomy.gov 2024-2025: 30-31 kWh/100mi",
     "GROSS used", "OK (30=0.186)"),
    ("Ariya", "Nissan", "Venture+ FWD 87kWh",
     87, 87, "Wikipedia: Nissan Ariya (87 kWh usable, extended range)",
     33, 0.195, "EPA fueleconomy.gov 2024: 33-34 kWh/100mi",
     "CORRECT", "OK (33=0.205)"),

    # ── Hyundai ────────────────────────────────────────────────────────────
    ("Ioniq 5", "Hyundai", "Long Range (77.4 kWh gross)",
     74, 77, "Wikipedia: Hyundai Ioniq 5 (77.4 kWh gross; ~74 usable est.)",
     30, 0.185, "EPA fueleconomy.gov 2025: 29-34 kWh/100mi",
     "GROSS used", "OK (30=0.186)"),
    ("Ioniq 6", "Hyundai", "Long Range RWD",
     74, 77, "Wikipedia / ev-database.org (77.4 kWh gross; ~74 usable)",
     24, 0.160, "EPA fueleconomy.gov 2024: 24-28 kWh/100mi",
     "GROSS used", "OK (24=0.149)"),
    ("Kona Electric", "Hyundai", "Long Range",
     65, 64, "ev-database.org (65.4 kWh usable, Long Range)",
     29, 0.170, "EPA fueleconomy.gov 2025: 29-31 kWh/100mi",
     "CLOSE (-2%)", "OK (29=0.180)"),

    # ── Kia ────────────────────────────────────────────────────────────────
    ("EV6", "Kia", "Long Range RWD",
     74, 77, "ev-database.org (77.4 kWh gross; ~74 usable, shared w/ Ioniq 5)",
     29, 0.185, "EPA fueleconomy.gov 2024: 29-35 kWh/100mi",
     "GROSS used", "OK (29=0.180)"),
    ("EV9", "Kia", "Long Range AWD",
     100, 100, "Wikipedia: Kia EV9 (99.8 kWh Long Range)",
     41, 0.230, "EPA fueleconomy.gov 2024-2025: 41-42 kWh/100mi",
     "CORRECT", "OK (41=0.255, LOW)"),
    ("Niro EV", "Kia", "2024+",
     65, 64, "ev-database.org (64.8 kWh usable)",
     30, 0.175, "EPA fueleconomy.gov 2025: 30 kWh/100mi",
     "CLOSE (-2%)", "OK (30=0.186)"),

    # ── BMW ────────────────────────────────────────────────────────────────
    ("iX", "BMW", "xDrive50",
     105, 77, "Wikipedia: BMW iX (105 kWh usable xDrive50; 71 kWh xDrive40)",
     39, 0.210, "EPA fueleconomy.gov 2024-2025: 39-44 kWh/100mi",
     "WRONG (xDrive40 used)", "OK (39=0.242)"),
    ("i4", "BMW", "eDrive40",
     81, 84, "Wikipedia / ev-database.org (81.2 kWh usable)",
     30, 0.190, "EPA fueleconomy.gov 2025: 29-34 kWh/100mi",
     "CLOSE (+3%)", "OK (30=0.186)"),
    ("i5", "BMW", "eDrive40",
     81, 84, "Wikipedia / ev-database.org (81.3 kWh usable)",
     32, 0.195, "EPA fueleconomy.gov 2025: 32-34 kWh/100mi",
     "CLOSE (+3%)", "OK (32=0.199)"),

    # ── Mercedes-Benz ──────────────────────────────────────────────────────
    ("EQE", "Mercedes-Benz", "350+",
     91, 90, "Wikipedia: Mercedes EQE (90.6 kWh usable)",
     35, 0.200, "EPA fueleconomy.gov 2024: 35 kWh/100mi",
     "CORRECT", "OK (35=0.217)"),
    ("EQS", "Mercedes-Benz", "450+",
     108, 108, "Wikipedia / ev-database.org (107.8 kWh usable)",
     34, 0.195, "EPA fueleconomy.gov 2025: 34-35 kWh/100mi",
     "CORRECT", "OK (34=0.211)"),
    ("EQB", "Mercedes-Benz", "250+",
     67, 66, "ev-database.org (66.5 kWh usable)",
     31, 0.215, "EPA fueleconomy.gov 2025: 31 kWh/100mi",
     "CLOSE (-1%)", "HIGH (31=0.193)"),

    # ── Volkswagen ─────────────────────────────────────────────────────────
    ("ID.4", "Volkswagen", "Pro / Pro S (RWD)",
     77, 77, "Wikipedia: VW ID.4 (77 kWh usable, Pro)",
     30, 0.195, "EPA fueleconomy.gov 2025: 30-33 kWh/100mi",
     "CORRECT", "OK (30=0.186)"),

    # ── Porsche ────────────────────────────────────────────────────────────
    ("Taycan", "Porsche", "Performance Battery Plus (2024)",
     84, 93, "Wikipedia: Porsche Taycan (83.7 kWh usable PB+, 2024)",
     39, 0.200, "EPA fueleconomy.gov 2024-2025: 39-45 kWh/100mi",
     "WRONG (gross used)", "OK (39=0.242)"),
    ("Macan Electric", "Porsche", "4 / Turbo",
     95, 100, "ev-database.org (94.9 kWh usable); Wikipedia",
     34, 0.215, "EPA fueleconomy.gov 2025: 34 kWh/100mi",
     "CLOSE (+5%)", "OK (34=0.211)"),

    # ── Toyota / Subaru / Honda / Lexus / Acura ────────────────────────────
    ("bZ4X", "Toyota", "FWD",
     71, 72, "ev-database.org (71.4 kWh usable)",
     28, 0.195, "EPA fueleconomy.gov 2025: 28-32 kWh/100mi",
     "CLOSE (+1%)", "OK (28=0.174, HIGH)"),
    ("Solterra", "Subaru", "AWD",
     71, 72, "ev-database.org (same platform as bZ4X, 71.4 kWh usable)",
     32, 0.200, "EPA fueleconomy.gov 2025: 32-33 kWh/100mi",
     "CLOSE (+1%)", "OK (32=0.199)"),
    ("Prologue", "Honda", "FWD",
     85, 85, "Wikipedia: Honda Prologue (85 kWh Ultium)",
     33, 0.195, "EPA fueleconomy.gov 2025: 33-34 kWh/100mi",
     "CORRECT", "OK (33=0.205)"),
    ("RZ", "Lexus", "300e / 450e",
     72, 72, "ev-database.org (71.4 kWh usable, shared bZ4X platform)",
     27, 0.200, "EPA fueleconomy.gov 2025: 27-31 kWh/100mi",
     "CORRECT", "OK (RZ 300e: 27=0.168, HIGH)"),
    ("ZDX", "Acura", "AWD / Type S",
     102, 102, "Wikipedia / ev-database.org (102 kWh, Ultium platform)",
     39, 0.220, "EPA fueleconomy.gov 2024: 39-43 kWh/100mi",
     "CORRECT", "OK (39=0.242)"),
]


class StyledPDF(FPDF):
    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_title = title
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, self.doc_title, align="L")
        self.cell(0, 8, f"Updated: {date.today().isoformat()}", align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def main():
    pdf = StyledPDF("UrbanEV-v2 EV Specifications Reference",
                    orientation="L", unit="mm", format="A4")
    pdf.alias_nb_pages()

    # ── Title Page ──
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 15, "Electric Vehicle Specifications", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Verified Reference for UrbanEV-v2 Simulation", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Last updated: {date.today().isoformat()}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "38 vehicle models verified against EPA and manufacturer data",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 6,
        "Primary Sources:\n"
        "  [1] EPA fueleconomy.gov - Official US EPA energy consumption ratings (kWh/100mi)\n"
        "  [2] Wikipedia - Vehicle specifications (battery capacity, sourced from OEM filings)\n"
        "  [3] ev-database.org - Usable battery capacity database\n"
        "  [4] Manufacturer specification sheets (Tesla, Ford, GM, Hyundai/Kia, BMW, etc.)\n\n"
        "Note: Battery capacity values should use USABLE (net) capacity, not gross. EPA consumption\n"
        "is the combined city/highway rating in kWh/100mi, converted to kWh/km by dividing by 160.934.\n"
        "Some values flagged for correction in the simulation script.",
        align="L")

    # ── Data Table ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 8, "Battery Capacity Verification", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Table header
    col_w = [30, 28, 35, 22, 22, 18, 18, 95]
    headers = ["Make", "Model", "Trim", "Verified\nkWh", "Script\nkWh", "Diff\n%", "Status", "Source"]
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(230, 235, 245)
    pdf.set_text_color(30, 30, 30)
    h = 8
    for hdr, w in zip(headers, col_w):
        pdf.cell(w, h, hdr, border=1, fill=True, align="C")
    pdf.ln(h)

    pdf.set_font("Helvetica", "", 6.5)
    for s in SPECS:
        model, make, trim, v_bat, o_bat, bat_src, epa_100mi, o_cons, cons_src, v_bat_s, v_cons_s = s
        diff_pct = round((o_bat - v_bat) / v_bat * 100) if v_bat else 0

        # Color code status
        if "WRONG" in v_bat_s:
            pdf.set_fill_color(255, 200, 200)
        elif "LOW" in v_bat_s or "HIGH" in v_bat_s:
            pdf.set_fill_color(255, 230, 200)
        elif "CLOSE" in v_bat_s or "GROSS" in v_bat_s or "SR ONLY" in v_bat_s:
            pdf.set_fill_color(255, 255, 210)
        else:
            pdf.set_fill_color(210, 255, 210)

        row_h = 5.5
        pdf.cell(col_w[0], row_h, make, border=1)
        pdf.cell(col_w[1], row_h, model, border=1)
        pdf.cell(col_w[2], row_h, trim[:22], border=1)
        pdf.cell(col_w[3], row_h, str(v_bat), border=1, align="C")
        pdf.cell(col_w[4], row_h, str(o_bat), border=1, align="C")
        pdf.cell(col_w[5], row_h, f"{diff_pct:+d}%", border=1, align="C")
        pdf.cell(col_w[6], row_h, v_bat_s[:12], border=1, align="C", fill=True)
        pdf.cell(col_w[7], row_h, bat_src[:60], border=1)
        pdf.ln(row_h)

    # ── Consumption Table ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 8, "EPA Energy Consumption Verification", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    col_w2 = [28, 26, 22, 22, 22, 22, 18, 108]
    headers2 = ["Make", "Model", "EPA\nkWh/100mi", "EPA\nkWh/km", "Script\nkWh/km", "Diff\n%", "Status", "Source"]
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(230, 235, 245)
    for hdr, w in zip(headers2, col_w2):
        pdf.cell(w, h, hdr, border=1, fill=True, align="C")
    pdf.ln(h)

    pdf.set_font("Helvetica", "", 6.5)
    for s in SPECS:
        model, make, trim, v_bat, o_bat, bat_src, epa_100mi, o_cons, cons_src, v_bat_s, v_cons_s = s
        epa_kwh_km = round(epa_100mi / 160.934, 3)
        diff_pct = round((o_cons - epa_kwh_km) / epa_kwh_km * 100) if epa_kwh_km else 0

        if abs(diff_pct) > 15:
            pdf.set_fill_color(255, 200, 200)
        elif abs(diff_pct) > 8:
            pdf.set_fill_color(255, 230, 200)
        elif abs(diff_pct) > 3:
            pdf.set_fill_color(255, 255, 210)
        else:
            pdf.set_fill_color(210, 255, 210)

        row_h = 5.5
        pdf.cell(col_w2[0], row_h, make, border=1)
        pdf.cell(col_w2[1], row_h, model, border=1)
        pdf.cell(col_w2[2], row_h, str(epa_100mi), border=1, align="C")
        pdf.cell(col_w2[3], row_h, f"{epa_kwh_km:.3f}", border=1, align="C")
        pdf.cell(col_w2[4], row_h, f"{o_cons:.3f}", border=1, align="C")
        pdf.cell(col_w2[5], row_h, f"{diff_pct:+d}%", border=1, align="C")
        pdf.cell(col_w2[6], row_h, v_cons_s[:12], border=1, align="C", fill=True)
        pdf.cell(col_w2[7], row_h, cons_src[:68], border=1)
        pdf.ln(row_h)

    # ── Correction Summary ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 8, "Required Corrections to convert_synpop_to_matsim.py",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    corrections = [
        ("Model Y", "Battery", "75 -> 81", "Using 60 kWh SR value; should be 81 kWh LR AWD (most common)"),
        ("Model 3", "Battery", "60 -> 78", "Using old/SR value; should be 78 kWh (Highland LR)"),
        ("Model S", "Battery", "100 -> 95", "Gross capacity; usable is 95 kWh"),
        ("Model X", "Battery", "100 -> 95", "Gross capacity; usable is 95 kWh"),
        ("F-150 Lightning", "Battery", "98 -> 131", "98 is Standard Range; Extended Range (131 kWh) is most common"),
        ("Mustang Mach-E", "Battery", "72 -> 88", "72 is Standard Range usable; ER usable is 88 kWh"),
        ("Bolt EV/EUV", "Battery", "65 -> 66", "Minor: actual is 66 kWh (2020+)"),
        ("Silverado EV", "Battery", "200 -> 205", "Minor: actual max range is 205 kWh"),
        ("Lyriq", "Battery", "102 -> 100", "102 is gross; usable is 100 kWh"),
        ("Ioniq 5", "Battery", "77 -> 74", "77.4 is gross; usable ~74 kWh"),
        ("Ioniq 6", "Battery", "77 -> 74", "77.4 is gross; usable ~74 kWh"),
        ("EV6", "Battery", "77 -> 74", "Same Hyundai E-GMP platform as Ioniq 5"),
        ("iX", "Battery", "77 -> 105", "77 is xDrive40; xDrive50 (most common in US) is 105 kWh"),
        ("i4", "Battery", "84 -> 81", "84 is gross; usable is 81.2 kWh"),
        ("i5", "Battery", "84 -> 81", "84 is gross; usable is 81.3 kWh"),
        ("Taycan", "Battery", "93 -> 84", "93.4 is gross PB+; usable is 83.7 kWh (2024)"),
        ("Macan Electric", "Battery", "100 -> 95", "100 is gross; usable is 94.9 kWh"),
        ("Leaf", "Battery", "40 -> 39", "Minor: usable is 39 kWh (40 gross)"),
    ]

    col_w3 = [30, 20, 30, 185]
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(230, 235, 245)
    for hdr, w in zip(["Model", "Field", "Change", "Reason"], col_w3):
        pdf.cell(w, 7, hdr, border=1, fill=True, align="C")
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 7)
    for model, field, change, reason in corrections:
        pdf.cell(col_w3[0], 5.5, model, border=1)
        pdf.cell(col_w3[1], 5.5, field, border=1, align="C")
        pdf.cell(col_w3[2], 5.5, change, border=1, align="C")
        pdf.cell(col_w3[3], 5.5, reason[:115], border=1)
        pdf.ln(5.5)

    # ── References ──
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 8, "References", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    refs = [
        "[1] U.S. EPA, 'Fuel Economy Guide - Electric Vehicles,' fueleconomy.gov, 2024-2025.",
        "    URL: https://www.fueleconomy.gov/feg/PowerSearch.do?action=alts&path=7&year1=2024&year2=2025&vtype=Electric",
        "[2] Wikipedia contributors, individual vehicle articles (Tesla Model Y, Model 3, Cybertruck,",
        "    Ford F-150 Lightning, Mustang Mach-E, Chevrolet Bolt, GMC Hummer EV, BMW iX, Porsche Taycan, etc.)",
        "    Accessed April 2026. Battery specs sourced from manufacturer filings and EPA certification data.",
        "[3] EV Database, 'Useable Battery Capacity,' ev-database.org, 2025.",
        "    URL: https://ev-database.org/cheatsheet/useable-battery-capacity-electric-car",
        "[4] U.S. DOE Alternative Fuels Data Center, 'Electric Vehicle Search,' afdc.energy.gov, 2025.",
        "    URL: https://afdc.energy.gov/vehicles/search/results?fuel_type=ELEC",
    ]
    for ref in refs:
        pdf.cell(0, 4.5, ref, new_x="LMARGIN", new_y="NEXT")

    pdf.output("/Users/tomal/Documents/URBAN EV Version 2_Reframed/ev_specifications_reference.pdf")
    print("Written: ev_specifications_reference.pdf")


if __name__ == "__main__":
    main()
