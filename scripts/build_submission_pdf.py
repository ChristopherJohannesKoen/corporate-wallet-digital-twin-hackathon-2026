from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
WALLET = json.loads((ROOT / "dashboard/app/data/wallet-v311-fixture.json").read_text(encoding="utf-8"))
V31 = json.loads((ROOT / "dashboard/app/data/v31-fixture.json").read_text(encoding="utf-8"))
SENS = json.loads((ROOT / "outputs/v2_validation/measurement_policy_sensitivity.json").read_text(encoding="utf-8"))
GENAI = json.loads((ROOT / "outputs/v2_validation/live_provider_comparison.json").read_text(encoding="utf-8"))
PROMOTION = json.loads((ROOT / "dashboard/app/data/promotion-fixture.json").read_text(encoding="utf-8"))
SUBMISSION = json.loads((ROOT / "config/submission.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

P = WALLET["projection"]
DETAILS = WALLET["details"]
BHP = DETAILS["E01-trade-finance"]["cell"]
PLAN = V31["projection"]["coverage_plan"]["entries"]
NAVY = HexColor("#07192A")
INK = HexColor("#102033")
MUTED = HexColor("#607286")
LINE = HexColor("#D8E1EA")
PANEL = HexColor("#F3F7FA")
BLUE = HexColor("#0B6CE2")
TEAL = HexColor("#11957D")
AMBER = HexColor("#D39B36")
VIOLET = HexColor("#6556D9")
PALE = HexColor("#EEF5FB")


def money(value: float) -> str:
    if abs(value) >= 1e9:
        return f"R{value / 1e9:.3f}bn"
    if abs(value) >= 1e6:
        return f"R{value / 1e6:.3f}m"
    return f"R{value:,.0f}"


def wrap(text: str, font: str, size: float, width: float, max_lines: int) -> list[str]:
    out: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                out.append(current)
            current = word
        if len(out) == max_lines:
            break
    if current and len(out) < max_lines:
        out.append(current)
    return out


def draw_wrap(c: canvas.Canvas, text: str, x: float, y: float, width: float, *, font="Helvetica", size=7, color=MUTED, leading=None, max_lines=3) -> None:
    c.setFont(font, size)
    c.setFillColor(color)
    for i, line in enumerate(wrap(text, font, size, width, max_lines)):
        c.drawString(x, y - i * (leading or size * 1.3), line)


def label(c: canvas.Canvas, text: str, x: float, y: float, color=BLUE) -> None:
    c.setFont("Helvetica-Bold", 6.2)
    c.setFillColor(color)
    c.drawString(x, y, text.upper())


def metric(c: canvas.Canvas, x: float, y: float, width: float, value: str, title: str, note: str, accent) -> None:
    c.setStrokeColor(accent)
    c.setLineWidth(2.4)
    c.line(x, y + 51, x + width, y + 51)
    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(INK)
    c.drawString(x, y + 29, value)
    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(x, y + 16, title.upper())
    draw_wrap(c, note, x, y + 6, width, size=5.5, max_lines=2)


c = canvas.Canvas(str(OUTPUT), pagesize=A4)
W, H = A4
c.setTitle("Corporate Wallet Digital Twin V3.2.0 — Hackathon One-Pager")
c.setAuthor(", ".join(SUBMISSION["team_members"]))

# Header: problem and answer.
c.setFillColor(NAVY)
c.rect(0, H - 150, W, 150, fill=1, stroke=0)
c.setFont("Helvetica-Bold", 6.5)
c.setFillColor(HexColor("#78B6FF"))
c.drawString(32, H - 24, "STANDARD BANK HACKATHON 2026  /  V3.2.0")
c.setFont("Helvetica-Bold", 24)
c.setFillColor(white)
c.drawString(32, H - 58, "Corporate Wallet Digital Twin")
c.setFont("Helvetica-Bold", 13)
c.setFillColor(HexColor("#D5E3F2"))
c.drawString(32, H - 84, "See the wallet. Size the gap. Choose the conversation.")
c.setFont("Helvetica-Bold", 19)
c.setFillColor(white)
c.drawString(377, H - 70, "A  =  q  ×  T")
c.setFont("Helvetica", 6.3)
c.setFillColor(HexColor("#AFC4D8"))
c.drawString(370, H - 88, "observed    share    total wallet")
c.setStrokeColor(HexColor("#294864"))
c.line(32, H - 104, 557, H - 104)
c.setFont("Helvetica-Bold", 7)
c.setFillColor(white)
c.drawString(32, H - 121, "COMMERCIAL ANSWER")
draw_wrap(c, "Syn Bank activity plus approved public anchors and governed priors estimate total-wallet and share intervals; a target-share scenario sizes the contestable gap; the Decision Twin turns it into a governed RM conversation.", 125, H - 119, 432, size=6.8, color=HexColor("#C5D4E4"), max_lines=2)
c.setFont("Helvetica", 5.6)
c.setFillColor(HexColor("#95AAC0"))
c.drawString(32, H - 142, "TEAM: Corporate Wallet Digital Twin  |  Christopher Koen  |  AS OF 30 JUNE 2026")

# Estate and governance metrics.
left = 32
cw = W - 64
my = H - 220
mw = (cw - 30) / 4
metric(c, left, my, mw, "3.064m", "supplied rows", "private evaluator mode", BLUE)
metric(c, left + mw + 10, my, mw, "20 × 5", "wallet heatmap", "100 client-product cells", TEAL)
metric(c, left + 2 * (mw + 10), my, mw, "15 / 85", "anchored / prior-led", "approval authoritative", AMBER)
metric(c, left + 3 * (mw + 10), my, mw, "31 / 51", "approved / pending facts", "82 source facts total", VIOLET)

# Estimation chain.
y = H - 252
c.setFont("Helvetica-Bold", 11)
c.setFillColor(INK)
c.drawString(left, y, "The estimation chain")
stages = [
    ("1  OBSERVE", "A by client × product", BLUE),
    ("2  IDENTIFY", "bounds from A and constraints", TEAL),
    ("3  ESTIMATE", "posterior T and q intervals", VIOLET),
    ("4  CONTEST", "G=max(q*·T−A,0)", AMBER),
    ("5  ACT", "problem, role, bundle, timing", BLUE),
]
sy = y - 58
sw = (cw - 24) / 5
for i, (title, copy, color) in enumerate(stages):
    x = left + i * (sw + 6)
    c.setFillColor(PANEL)
    c.rect(x, sy, sw, 46, fill=1, stroke=0)
    c.setStrokeColor(color)
    c.setLineWidth(2)
    c.line(x, sy + 46, x + sw, sy + 46)
    c.setFont("Helvetica-Bold", 6.2)
    c.setFillColor(color)
    c.drawString(x + 7, sy + 29, title)
    draw_wrap(c, copy, x + 7, sy + 17, sw - 14, size=5.5, color=MUTED, max_lines=2)

# BHP proof.
by = 372
c.setFillColor(NAVY)
c.rect(left, by, cw, 127, fill=1, stroke=0)
label(c, "BHP TRADE FINANCE — FORENSIC CELL", left + 14, by + 106, HexColor("#78B6FF"))
c.setFont("Helvetica-Bold", 14)
c.setFillColor(white)
c.drawString(left + 14, by + 82, f"A {money(float(BHP['observed_activity']['amount']))}")
c.drawString(left + 132, by + 82, f"T {money(BHP['posterior_wallet']['lower'])}–{money(BHP['posterior_wallet']['upper'])}")
c.drawString(left + 341, by + 82, f"q {BHP['share_interval']['lower']*100:.1f}–{BHP['share_interval']['upper']*100:.1f}%")
c.setFont("Helvetica", 6.2)
c.setFillColor(HexColor("#AFC4D8"))
c.drawString(left + 14, by + 67, "observed Syn Bank annual activity")
c.drawString(left + 132, by + 67, f"posterior total-wallet P10–P90 · P50 {money(BHP['posterior_wallet']['median'])}")
c.drawString(left + 341, by + 67, f"estimated bank share · P50 {BHP['share_interval']['median']*100:.1f}%")
c.setStrokeColor(HexColor("#31506D"))
c.line(left + 14, by + 51, left + cw - 14, by + 51)
c.setFont("Helvetica-Bold", 8)
c.setFillColor(HexColor("#78B6FF"))
c.drawString(left + 14, by + 33, f"q* {BHP['target_share_scenario']*100:.0f}% scenario")
c.setFillColor(HexColor("#5BE0BF"))
c.drawString(left + 142, by + 33, f"G P50 {money(BHP['contestable_activity']['median'])}")
c.setFillColor(HexColor("#F0BF62"))
c.drawString(left + 307, by + 33, f"Contribution P50 {money(BHP['scenario_contribution']['median'])}")
c.setFont("Helvetica", 5.8)
c.setFillColor(HexColor("#AFC4D8"))
c.drawString(left + 14, by + 15, "E1 approved · POSTERIOR share, not measured competitor share · representative economics, not bank-approved pricing")

# Decision action and GenAI.
py = 224
pw = (cw - 12) / 2
c.setFillColor(PALE)
c.rect(left, py, pw, 134, fill=1, stroke=0)
label(c, "DECISION TWIN ACTION", left + 13, py + 115)
c.setFont("Helvetica-Bold", 11)
c.setFillColor(INK)
c.drawString(left + 13, py + 94, "Eight discovery conversations")
draw_wrap(c, "Wallet gap → stakeholder role → business problem → solution bundle → 30/60/90-day timing → highest-positive-net-VOI question.", left + 13, py + 77, pw - 26, size=6.6, max_lines=3)
c.setFont("Helvetica-Bold", 6.7)
c.setFillColor(TEAL)
c.drawString(left + 13, py + 43, "PERMITTED NOW")
draw_wrap(c, "Validate wallet, stakeholder and feasibility.", left + 13, py + 30, pw - 26, font="Helvetica-Bold", size=7.3, color=INK, max_lines=2)
c.setFont("Helvetica", 5.6)
c.setFillColor(MUTED)
c.drawString(left + 13, py + 10, "Conditional product action only after missing facts and required gates are confirmed.")

rx = left + pw + 12
c.setFillColor(HexColor("#F4F0FF"))
c.rect(rx, py, pw, 134, fill=1, stroke=0)
label(c, "GROUNDED GENAI PROOF", rx + 13, py + 115, VIOLET)
c.setFont("Helvetica-Bold", 11)
c.setFillColor(INK)
c.drawString(rx + 13, py + 94, "Closed pack → Why / How / What")
draw_wrap(c, "Numbers, signs, currencies, citations, rank and graph path stay deterministic. Provider failure always returns the deterministic brief.", rx + 13, py + 77, pw - 26, size=6.6, max_lines=3)
c.setFont("Helvetica-Bold", 7)
c.setFillColor(VIOLET)
c.drawString(rx + 13, py + 43, "9 COMPARATIVE TARGET RUNS · 0 EXECUTED")
draw_wrap(c, "Fresh rotated credentials and explicit acknowledgement are required; access failure is not presented as success.", rx + 13, py + 28, pw - 26, size=5.8, max_lines=3)

# Evidence and limitation box.
ly = 78
c.setFillColor(PANEL)
c.rect(left, ly, cw, 132, fill=1, stroke=0)
label(c, "WHAT THE SENSITIVITY SAYS", left + 13, ly + 113, TEAL)
c.setFont("Helvetica-Bold", 9.5)
c.setFillColor(INK)
c.drawString(left + 13, ly + 94, "Trade Finance: first-ranked in 100% of 10,000 draws")
c.setFont("Helvetica", 5.8)
c.setFillColor(MUTED)
c.drawString(left + 13, ly + 79, "Not a release condition; E1 weight sensitivity changes its top-10 share.")

px = left + 292
label(c, "PROMOTION READINESS TWIN", px, ly + 113, VIOLET)
c.setFont("Helvetica-Bold", 9.5)
c.setFillColor(INK)
c.drawString(px, ly + 94, f"PMR {PROMOTION['summary']['promotion_machinery_readiness']:.0%}  ·  BER {PROMOTION['summary']['bank_evidence_readiness']:.0%}  ·  {PROMOTION['clock']['consecutive_clean_rehearsal_days']} virtual / {PROMOTION['clock']['elapsed_bank_shadow_days']} bank days")
c.setFont("Helvetica", 5.8)
c.setFillColor(MUTED)
c.drawString(px, ly + 79, f"Real {PROMOTION['summary']['real_state']} · rehearsed {PROMOTION['summary']['rehearsed_state']}")
c.setStrokeColor(LINE)
c.line(left + 13, ly + 65, left + cw - 13, ly + 65)
label(c, "LIMITATION — REHEARSAL CAN NEVER AUTHORIZE BANK USE", left + 13, ly + 49, AMBER)
draw_wrap(c, "The 51 pending facts stay excluded. No E3 panel, approved bank economics, bank infrastructure, RM pilot or randomized outcome history exists. BANK_SHADOW_AUTHORIZED remains FALSE; measured share and causal value stay disabled.", left + 13, ly + 34, cw - 26, size=6.2, max_lines=3)

# Footer.
c.setStrokeColor(LINE)
c.line(left, 64, W - left, 64)
c.setFont("Helvetica-Bold", 5.7)
c.setFillColor(INK)
c.drawString(left, 51, "BUILD: python scripts/build_submission.py  |  Public mirror contains independently generated anonymized data only")
c.setFont("Helvetica", 5.3)
c.setFillColor(MUTED)
c.drawString(left, 38, SUBMISSION["repository_url"])
c.drawString(left, 25, "Version 3.2.0  |  Data boundary: confidential Syn Bank activity + approved public E1 + governed priors  |  FX and Liquidity are labelled proxies")
c.drawRightString(W - left, 12, "Corporate Wallet Digital Twin · Christopher Koen")
c.showPage()
c.save()
print(json.dumps({"status": "ok", "output": str(OUTPUT), "pages": 1, "version": "3.2.0"}, indent=2))
