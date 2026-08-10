from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
PORTFOLIO = json.loads((ROOT / "outputs" / "data" / "portfolio.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "outputs" / "client_demo" / "client_demo_data_manifest.json").read_text(encoding="utf-8"))
GENAI = json.loads((ROOT / "outputs" / "v2_validation" / "genai_golden_eval.json").read_text(encoding="utf-8"))
FIXTURE = json.loads((ROOT / "dashboard" / "app" / "data" / "shadow-fixture.json").read_text(encoding="utf-8"))
V3 = json.loads((ROOT / "dashboard" / "app" / "data" / "v3-fixture.json").read_text(encoding="utf-8"))
SUBMISSION = json.loads((ROOT / "config" / "submission.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "output" / "pdf" / "Corporate-Wallet-Digital-Twin-One-Pager.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = HexColor("#071321")
INK = HexColor("#0C1728")
MUTED = HexColor("#627086")
LINE = HexColor("#D7DEE8")
PANEL = HexColor("#F1F4F8")
PALE_BLUE = HexColor("#EAF3FF")
BLUE = HexColor("#0B63E5")
TEAL = HexColor("#008B83")
AMBER = HexColor("#E2951C")
VIOLET = HexColor("#7658D6")


def pct(value: float, digits: int = 0) -> str:
    return f"{100 * value:.{digits}f}%"


def money(value: float, digits: int = 1) -> str:
    if abs(value) >= 1e9:
        return f"R{value / 1e9:.{digits}f}bn"
    if abs(value) >= 1e6:
        return f"R{value / 1e6:.{digits}f}m"
    return f"R{value:,.0f}"


def wrap_lines(text: str, font: str, size: float, width: float, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def draw_wrapped(c: canvas.Canvas, text: str, x: float, y: float, width: float, *, font: str = "Helvetica", size: float = 8, color=MUTED, leading: float | None = None, max_lines: int = 4) -> float:
    leading = leading or size * 1.25
    c.setFont(font, size)
    c.setFillColor(color)
    lines = wrap_lines(text, font, size, width, max_lines)
    for index, line_text in enumerate(lines):
        c.drawString(x, y - index * leading, line_text)
    return y - len(lines) * leading


def small_label(c: canvas.Canvas, text: str, x: float, y: float, color=BLUE) -> None:
    c.setFont("Helvetica-Bold", 6.4)
    c.setFillColor(color)
    c.drawString(x, y, text.upper())


def metric(c: canvas.Canvas, x: float, y: float, width: float, value: str, title: str, accent) -> None:
    c.setStrokeColor(accent)
    c.setLineWidth(2.4)
    c.line(x, y + 53, x + width, y + 53)
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(INK)
    c.drawString(x, y + 30, value)
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(x, y + 15, title)


lhs = FIXTURE["sensitivity"]
tf_global = lhs["product_summary"]["Trade finance"]
fx_global = lhs["product_summary"]["Cross-border FX"]
action_portfolio = V3["action_portfolio"]
top3 = action_portfolio["selected_actions"][:3]
glencore = next(row for row in V3["opportunities"] if row["opportunity_id"] == "E02-trade-finance")
voi = V3["evidence_acquisition"]

c = canvas.Canvas(str(OUTPUT), pagesize=A4)
W, H = A4
c.setTitle("Corporate Wallet Digital Twin V3.0 - Hackathon One-Pager")
c.setAuthor(", ".join(SUBMISSION["team_members"]))

# Header.
c.setFillColor(NAVY)
c.rect(0, H - 164, W, 164, fill=1, stroke=0)
cover = ROOT / "dashboard" / "public" / "og.png"
if cover.exists():
    c.saveState()
    clip = c.beginPath()
    clip.rect(W * 0.61, H - 164, W * 0.39, 164)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(ImageReader(str(cover)), W * 0.55, H - 176, width=W * 0.52, height=190, preserveAspectRatio=True, anchor="c", mask="auto")
    c.restoreState()
    c.setFillColor(NAVY)
    c.rect(0, H - 164, W * 0.66, 164, fill=1, stroke=0)
c.setFont("Helvetica-Bold", 6.5)
c.setFillColor(HexColor("#7CB6FF"))
c.drawString(34, H - 25, "STANDARD BANK HACKATHON 2026")
c.setFont("Helvetica-Bold", 25)
c.setFillColor(white)
c.drawString(34, H - 63, "Corporate Wallet Digital Twin")
c.setFont("Helvetica", 12.5)
c.setFillColor(HexColor("#C7D5E8"))
c.drawString(34, H - 91, "Reconstruct the unseen wallet. Decide what matters next.")
c.setStrokeColor(HexColor("#2D4C6D"))
c.line(34, H - 109, 347, H - 109)
c.setFont("Helvetica-Bold", 7.2)
c.setFillColor(white)
c.drawString(34, H - 126, f"TEAM: {SUBMISSION['team_name']}")
c.setFont("Helvetica", 7.2)
c.setFillColor(HexColor("#B9C8D9"))
c.drawString(34, H - 140, f"MEMBER: {', '.join(SUBMISSION['team_members'])}")
c.setFont("Helvetica-Bold", 5.8)
c.setFillColor(HexColor("#8FA5BD"))
c.drawString(34, H - 155, f"AS OF 10 AUGUST 2026  |  {SUBMISSION['solution_version']}  |  SYN BANK SIMULATION + PUBLIC E1")

# Proof row.
left = 34
content_w = W - 68
metric_y = H - 238
metric_w = (content_w - 30) / 4
metric(c, left, metric_y, metric_w, "1,500", "SHADOW-WALLET EDGES", BLUE)
metric(c, left + metric_w + 10, metric_y, metric_w, "100", "CLIENT-PRODUCT NETWORKS", TEAL)
metric(c, left + 2 * (metric_w + 10), metric_y, metric_w, "12", "CAPACITY-AWARE RM ACTIONS", AMBER)
metric(c, left + 3 * (metric_w + 10), metric_y, metric_w, "8", "POSITIVE-NET-VOI REQUESTS", VIOLET)

# Commercial decision.
decision_top = H - 264
c.setFont("Helvetica-Bold", 11.5)
c.setFillColor(INK)
c.drawString(left, decision_top, "The decision: allocate twelve RM actions under downside risk")
c.setFont("Helvetica", 7.4)
c.setFillColor(MUTED)
c.drawString(left, decision_top - 14, "Expected scenario value and lower-tail CVaR are optimized with client, product and sector capacity constraints.")

row_y = decision_top - 88
columns = [210, 115, 92, 90]
headers = ["CLIENT / PRODUCT", "EXPECTED", "DOWNSIDE CVAR", "NEED"]
positions = [left, left + columns[0], left + columns[0] + columns[1], left + columns[0] + columns[1] + columns[2]]
c.setFillColor(PANEL)
c.rect(left, row_y + 40, content_w, 21, fill=1, stroke=0)
for x, header in zip(positions, headers):
    c.setFont("Helvetica-Bold", 6.1)
    c.setFillColor(MUTED)
    c.drawString(x + 7, row_y + 48, header)
for index, row in enumerate(top3):
    y = row_y + 24 - index * 18
    c.setFont("Helvetica-Bold", 7.3)
    c.setFillColor(INK)
    c.drawString(positions[0] + 7, y, f"{index + 1}. {row['entity_name']} - {row['product']}")
    c.setFillColor(AMBER if row["product"] == "Trade finance" else BLUE)
    c.drawString(positions[1] + 7, y, money(row["expected_scenario_value_zar"]))
    c.setFillColor(INK)
    c.drawString(positions[2] + 7, y, money(row["downside_cvar_zar"]))
    c.setFillColor(TEAL)
    c.drawString(positions[3] + 7, y, pct(row["need_probability"]))

# Identification and BHP band.
band_y = 319
c.setFillColor(NAVY)
c.rect(left, band_y, 180, 75, fill=1, stroke=0)
c.setFont("Helvetica-Bold", 25)
c.setFillColor(white)
c.drawString(left + 16, band_y + 40, "A")
c.setFillColor(HexColor("#7CB6FF"))
c.drawString(left + 48, band_y + 40, "=")
c.setFillColor(white)
c.drawString(left + 78, band_y + 40, "q")
c.setFillColor(HexColor("#7CB6FF"))
c.drawString(left + 108, band_y + 40, "x")
c.setFillColor(white)
c.drawString(left + 138, band_y + 40, "T")
c.setFont("Helvetica", 6.2)
c.setFillColor(HexColor("#AFC0D4"))
c.drawString(left + 16, band_y + 17, "Observed = bank share x total wallet")

bhp_x = left + 194
c.setFillColor(PALE_BLUE)
c.rect(bhp_x, band_y, content_w - 194, 75, fill=1, stroke=0)
small_label(c, "GLENCORE TRADE FINANCE", bhp_x + 14, band_y + 59)
c.setFont("Helvetica-Bold", 11)
c.setFillColor(INK)
c.drawString(bhp_x + 14, band_y + 40, "Entropy-constrained Shadow Wallet")
c.setFont("Helvetica-Bold", 8.5)
c.setFillColor(BLUE)
c.drawString(bhp_x + 14, band_y + 21, f"Observed {money(glencore['shadow_wallet']['observed_bank_flow'])}")
c.setFillColor(AMBER)
c.drawString(bhp_x + 111, band_y + 21, f"Latent {money(glencore['shadow_wallet']['latent_external_wallet']['median'])}")
c.setFillColor(TEAL)
c.drawString(bhp_x + 209, band_y + 21, f"Share {pct(glencore['shadow_wallet']['bank_share']['median'], 1)}")
c.setFont("Helvetica", 5.8)
c.setFillColor(MUTED)
c.drawString(bhp_x + 14, band_y + 8, "256 draws | 5 corridors x 3 anonymous providers | exact median mass balance | SCENARIO, not measured")

# Evidence/model proof.
proof_y = 202
c.setFont("Helvetica-Bold", 11.5)
c.setFillColor(INK)
c.drawString(left, proof_y + 87, "V3 mechanics reconcile exactly without inventing empirical truth")
proofs = [
    ("R0", "maximum Shadow Wallet mass-balance error", BLUE),
    ("100", "Bayesian change-point series replayed", TEAL),
    ("8 / 8", "selected evidence requests have positive net VOI", VIOLET),
]
for index, (value, label, color) in enumerate(proofs):
    x = left + index * 174
    c.setStrokeColor(color)
    c.setLineWidth(2.4)
    c.line(x, proof_y + 66, x + 150, proof_y + 66)
    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(color)
    c.drawString(x, proof_y + 42, value)
    draw_wrapped(c, label, x, proof_y + 27, 150, font="Helvetica-Bold", size=6.6, color=INK, max_lines=2)
c.setFont("Helvetica", 5.8)
c.setFillColor(MUTED)
c.drawString(left, proof_y + 2, "Claim audit: 0 measured competitor-share claims | 0 causal-value claims | reconstructed leakage remains a modelled verification signal.")

# Sensitivity and GenAI.
bottom_y = 78
c.setFillColor(PANEL)
c.rect(left, bottom_y, 254, 97, fill=1, stroke=0)
small_label(c, "RATE / PRIOR SENSITIVITY", left + 13, bottom_y + 80, VIOLET)
c.setFont("Helvetica-Bold", 12)
c.setFillColor(INK)
c.drawString(left + 13, bottom_y + 59, "Trade Finance remains first-ranked")
c.setFont("Helvetica-Bold", 8)
c.setFillColor(VIOLET)
c.drawString(left + 13, bottom_y + 40, "9/9 benchmark cases | 100% of 10,000 draws")
draw_wrapped(c, f"But it is never a majority of the top 10. Cross-border FX is majority-dominant in {pct(fx_global['majority_dominance_frequency'], 1)} of draws.", left + 13, bottom_y + 24, 225, size=6.4, color=MUTED, max_lines=3)

right_x = left + 266
c.setFillColor(PALE_BLUE)
c.rect(right_x, bottom_y, content_w - 266, 97, fill=1, stroke=0)
small_label(c, "DECISION-DIRECTED RAG + GENAI", right_x + 13, bottom_y + 80, BLUE)
c.setFont("Helvetica-Bold", 12)
c.setFillColor(INK)
c.drawString(right_x + 13, bottom_y + 59, "Score -> value -> approve -> compile -> brief")
c.setFont("Helvetica-Bold", 8)
c.setFillColor(TEAL)
c.drawString(right_x + 13, bottom_y + 40, f"8 requests | {money(sum(row['net_value_of_information_zar'] for row in voi['selected']))} net VOI | 0 autonomous retrievals")
draw_wrapped(c, "Evidence is requested only when expected decision value exceeds acquisition cost and latency. The LLM sees a closed claim pack; deterministic fallback remains.", right_x + 13, bottom_y + 24, content_w - 292, size=6.4, color=MUTED, max_lines=3)

# Footer.
c.setStrokeColor(LINE)
c.setLineWidth(0.5)
c.line(left, 61, W - left, 61)
c.setFont("Helvetica-Bold", 5.9)
c.setFillColor(INK)
c.drawString(left, 49, "DELIVERED: executed V3 notebook | entitled decision lab | Shadow Wallet | BOCPD signals | robust portfolio | VOI queue | judging deck")
c.setFont("Helvetica", 5.2)
c.setFillColor(MUTED)
c.drawString(left, 37, "External gates: E3 multibank panel, bank-approved economics/infrastructure, live-provider evaluation and supervised RM trial.")
c.drawString(left, 26, "Data label: SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE PRIORS - RECONSTRUCTED COMPETITOR FLOWS ARE NOT MEASURED")
c.drawString(left, 15, f"Code: {SUBMISSION['repository_url']} (private repository - reviewer access required)")

c.showPage()
c.save()
print(json.dumps({"status": "ok", "output": str(OUTPUT), "pages": 1}, indent=2))
