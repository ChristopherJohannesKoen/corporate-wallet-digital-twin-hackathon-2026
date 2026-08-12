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
V31 = json.loads((ROOT / "dashboard/app/data/v31-fixture.json").read_text(encoding="utf-8"))
SUBMISSION = json.loads((ROOT / "config/submission.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

P = V31["projection"]
PLAN = P["coverage_plan"]["entries"]
CONVERSATIONS = V31["conversations"]
NAVY = HexColor("#081827")
INK = HexColor("#102033")
MUTED = HexColor("#65758A")
LINE = HexColor("#DCE4ED")
PANEL = HexColor("#F3F6FA")
PALE_BLUE = HexColor("#EAF3FF")
PALE_TEAL = HexColor("#E9F7F3")
BLUE = HexColor("#0872DF")
TEAL = HexColor("#168D72")
AMBER = HexColor("#C47C0A")
VIOLET = HexColor("#6256C7")
RED = HexColor("#BA3E4C")


def money(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    if abs(value) >= 1e9:
        return f"R{value / 1e9:.1f}bn"
    if abs(value) >= 1e6:
        return f"R{value / 1e6:.1f}m"
    if abs(value) >= 1e3:
        return f"R{value / 1e3:.1f}k"
    return f"R{value:,.0f}"


def pct(value: float, digits: int = 0) -> str:
    return f"{value * 100:.{digits}f}%"


def wrap(text: str, font: str, size: float, width: float, max_lines: int) -> list[str]:
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
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def draw_wrap(c: canvas.Canvas, text: str, x: float, y: float, width: float, *, font="Helvetica", size=7.2, color=MUTED, leading=None, max_lines=4) -> float:
    leading = leading or size * 1.25
    c.setFont(font, size)
    c.setFillColor(color)
    for index, line in enumerate(wrap(text, font, size, width, max_lines)):
        c.drawString(x, y - index * leading, line)
    return y - max_lines * leading


def label(c: canvas.Canvas, text: str, x: float, y: float, color=BLUE) -> None:
    c.setFont("Helvetica-Bold", 6.2)
    c.setFillColor(color)
    c.drawString(x, y, text.upper())


def metric(c: canvas.Canvas, x: float, y: float, width: float, value: str, title: str, note: str, accent) -> None:
    c.setStrokeColor(accent)
    c.setLineWidth(2.5)
    c.line(x, y + 54, x + width, y + 54)
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(INK)
    c.drawString(x, y + 32, value)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(x, y + 18, title.upper())
    draw_wrap(c, note, x, y + 8, width, size=5.7, max_lines=2)


c = canvas.Canvas(str(OUTPUT), pagesize=A4)
W, H = A4
c.setTitle("Corporate Wallet Digital Twin V3.1 - Hackathon One-Pager")
c.setAuthor(", ".join(SUBMISSION["team_members"]))

# Header
c.setFillColor(NAVY)
c.rect(0, H - 164, W, 164, fill=1, stroke=0)
cover = ROOT / "dashboard/public/og-v31.png"
if cover.exists():
    c.saveState()
    clip = c.beginPath()
    clip.rect(W * 0.65, H - 164, W * 0.35, 164)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(ImageReader(str(cover)), W * 0.58, H - 178, width=W * 0.51, height=190, preserveAspectRatio=True, anchor="c", mask="auto")
    c.restoreState()
    c.setFillColor(NAVY)
    c.rect(0, H - 164, W * 0.69, 164, fill=1, stroke=0)
c.setFont("Helvetica-Bold", 6.5)
c.setFillColor(HexColor("#7CB6FF"))
c.drawString(34, H - 24, "STANDARD BANK HACKATHON 2026  /  V3.1")
c.setFont("Helvetica-Bold", 24)
c.setFillColor(white)
c.drawString(34, H - 62, "Corporate Wallet Digital Twin")
c.setFont("Helvetica", 12)
c.setFillColor(HexColor("#C7D5E8"))
c.drawString(34, H - 90, "Turn partial evidence into the right client conversation.")
c.setStrokeColor(HexColor("#2D4C6D"))
c.line(34, H - 108, 358, H - 108)
c.setFont("Helvetica-Bold", 7.2)
c.setFillColor(white)
c.drawString(34, H - 125, f"TEAM: {SUBMISSION['team_name']}")
c.setFont("Helvetica", 7.2)
c.setFillColor(HexColor("#B9C8D9"))
c.drawString(34, H - 139, f"MEMBER: {', '.join(SUBMISSION['team_members'])}")
c.setFont("Helvetica-Bold", 5.8)
c.setFillColor(HexColor("#8FA5BD"))
c.drawString(34, H - 154, "AS OF 30 JUNE 2026  |  BUILD 12 AUGUST 2026  |  CLIENT DEMONSTRATION")

# Metrics
left = 34
content_w = W - 68
metric_y = H - 237
metric_w = (content_w - 30) / 4
metric(c, left, metric_y, metric_w, "20", "Business Twins", "12 components each", BLUE)
metric(c, left + metric_w + 10, metric_y, metric_w, "320", "Solution estimates", "16 solutions x 20 clients", TEAL)
metric(c, left + 2 * (metric_w + 10), metric_y, metric_w, "224", "Conversations", "all discovery-only", AMBER)
metric(c, left + 3 * (metric_w + 10), metric_y, metric_w, "8", "Weekly capacity", "MILP status OPTIMAL", VIOLET)

# Weekly decision table
decision_top = H - 270
c.setFont("Helvetica-Bold", 11.5)
c.setFillColor(INK)
c.drawString(left, decision_top, "The decision: spend eight conversations where downside-aware value is strongest")
c.setFont("Helvetica", 7.1)
c.setFillColor(MUTED)
c.drawString(left, decision_top - 14, "Pareto-filtered client problems and solution bundles; client and bank value remain separate; unknown feasibility means discovery.")
row_y = decision_top - 89
cols = [30, 130, 125, 75, 72, 64]
headers = ["#", "CLIENT / ROLE", "ISSUE / SOLUTION", "CLIENT", "BANK", "STABILITY"]
positions = [left]
for col in cols[:-1]:
    positions.append(positions[-1] + col)
c.setFillColor(PANEL)
c.rect(left, row_y + 42, content_w, 20, fill=1, stroke=0)
for x, header in zip(positions, headers):
    c.setFont("Helvetica-Bold", 5.8)
    c.setFillColor(MUTED)
    c.drawString(x + 4, row_y + 49, header)
for index, item in enumerate(PLAN[:5]):
    y = row_y + 28 - index * 17
    c.setFont("Helvetica-Bold", 6.6)
    c.setFillColor(INK)
    c.drawString(positions[0] + 4, y, str(item["rank"]))
    c.drawString(positions[1] + 4, y, f"{item['entity_name']} / {item['stakeholder_role'].replace('_', ' ').title()}")
    c.drawString(positions[2] + 4, y + 2, item["problem_label"])
    c.setFont("Helvetica", 5.6)
    c.setFillColor(MUTED)
    c.drawString(positions[2] + 4, y - 5, item["solution_label"])
    c.setFont("Helvetica-Bold", 6.6)
    c.setFillColor(TEAL)
    c.drawString(positions[3] + 4, y, money(item["client_value_median"]))
    c.setFillColor(VIOLET)
    c.drawString(positions[4] + 4, y, money(item["bank_value_median"]))
    c.setFillColor(AMBER)
    c.drawString(positions[5] + 4, y, pct(item["selection_stability"]))

# Core decision object and BHP proof
band_y = 297
c.setFillColor(NAVY)
c.rect(left, band_y, 185, 90, fill=1, stroke=0)
label(c, "CANONICAL DECISION OBJECT", left + 14, band_y + 71, HexColor("#7CB6FF"))
c.setFont("Helvetica-Bold", 10.5)
c.setFillColor(white)
c.drawString(left + 14, band_y + 51, "Client + stakeholder + problem")
c.drawString(left + 14, band_y + 37, "+ solution bundle + window")
c.setFont("Helvetica", 6.2)
c.setFillColor(HexColor("#AFC0D4"))
draw_wrap(c, "Product opportunity remains an analytical input, not the final banker action.", left + 14, band_y + 20, 157, size=6.0, color=HexColor("#AFC0D4"), max_lines=2)

bhp = next(item for item in PLAN if item["entity_name"] == "BHP Group")
bhp_conv = CONVERSATIONS[bhp["conversation_id"]]
bhp_x = left + 198
c.setFillColor(PALE_BLUE)
c.rect(bhp_x, band_y, content_w - 198, 90, fill=1, stroke=0)
label(c, "BHP EXPLANATION PATH", bhp_x + 14, band_y + 71)
c.setFont("Helvetica-Bold", 10.2)
c.setFillColor(INK)
c.drawString(bhp_x + 14, band_y + 52, f"{bhp['problem_label']} -> {bhp['stakeholder_role'].title()} -> {bhp['solution_label']}")
c.setFont("Helvetica-Bold", 7.5)
c.setFillColor(TEAL)
c.drawString(bhp_x + 14, band_y + 35, f"Client {money(bhp['client_value_median'])}")
c.setFillColor(VIOLET)
c.drawString(bhp_x + 104, band_y + 35, f"Bank {money(bhp['bank_value_median'])}")
c.setFillColor(AMBER)
c.drawString(bhp_x + 186, band_y + 35, f"Stability {pct(bhp['selection_stability'])}")
draw_wrap(c, bhp_conv["engagement_window"]["why_now"], bhp_x + 14, band_y + 20, content_w - 226, size=5.9, color=MUTED, max_lines=2)

# Evidence / controls / active learning
proof_y = 182
c.setFont("Helvetica-Bold", 11.3)
c.setFillColor(INK)
c.drawString(left, proof_y + 87, "Evidence-backed breadth, with the limits made visible")
proofs = [
    ("905", "typed business claims", BLUE),
    ("85 E1", "public evidence claims", TEAL),
    ("51", "facts pending SME review", AMBER),
    ("1,148", "immutable domain events", VIOLET),
]
for index, (value, title, color) in enumerate(proofs):
    x = left + index * 130
    c.setStrokeColor(color)
    c.setLineWidth(2.4)
    c.line(x, proof_y + 66, x + 112, proof_y + 66)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(color)
    c.drawString(x, proof_y + 43, value)
    c.setFont("Helvetica-Bold", 6.4)
    c.setFillColor(INK)
    c.drawString(x, proof_y + 29, title)
c.setFont("Helvetica", 5.8)
c.setFillColor(MUTED)
c.drawString(left, proof_y + 9, "0 measured competitor-share claims | 0 causal-value claims | 122 solution projections fail closed | all selected actions are discovery")

# Bottom panels
bottom_y = 73
c.setFillColor(PALE_TEAL)
c.rect(left, bottom_y, 255, 99, fill=1, stroke=0)
label(c, "ACTIVE COVERAGE LEARNING", left + 13, bottom_y + 82, TEAL)
c.setFillColor(INK)
draw_wrap(c, "Ask only when evidence can flip the decision", left + 13, bottom_y + 62, 225, font="Helvetica-Bold", size=10.5, color=INK, max_lines=2)
first_question = CONVERSATIONS[PLAN[0]["conversation_id"]]["next_best_question"]
c.setFont("Helvetica-Bold", 7.4)
c.setFillColor(TEAL)
c.drawString(left + 13, bottom_y + 35, f"{money(first_question['net_voi_zar'])} net VOI / 512 common draws")
draw_wrap(c, first_question["question_text"], left + 13, bottom_y + 18, 225, size=6.2, color=MUTED, max_lines=2)

right_x = left + 267
c.setFillColor(PALE_BLUE)
c.rect(right_x, bottom_y, content_w - 267, 99, fill=1, stroke=0)
label(c, "CONTROLLED GENAI + PRODUCTION SHAPE", right_x + 13, bottom_y + 82)
c.setFont("Helvetica-Bold", 11.2)
c.setFillColor(INK)
c.drawString(right_x + 13, bottom_y + 62, "Closed pack -> Why / How / What brief")
c.setFont("Helvetica-Bold", 7.2)
c.setFillColor(BLUE)
c.drawString(right_x + 13, bottom_y + 45, "Arithmetic, rank, VOI, paths and citations stay deterministic")
draw_wrap(c, "AWS/EKS + Delta/Unity Catalog + MLflow + MSK + OPA + OpenTelemetry are defined. Bank production remains NOT_PROMOTABLE.", right_x + 13, bottom_y + 30, content_w - 293, size=6.2, color=MUTED, max_lines=3)

# Footer
c.setStrokeColor(LINE)
c.setLineWidth(.5)
c.line(left, 61, W - left, 61)
c.setFont("Helvetica-Bold", 5.8)
c.setFillColor(INK)
c.drawString(left, 49, "DELIVERED: V3.1 Decision Twin API + workbench + 20 twins + 320 estimates + eight-conversation plan + executed notebook + governed artifacts")
c.setFont("Helvetica", 5.2)
c.setFillColor(MUTED)
c.drawString(left, 37, "Open gates: E3 multibank panel, approved economics, bank cloud/identity/security, live-provider adjudication, RM pilot, randomized trial, 30 clean shadow days.")
c.drawString(left, 26, "Data label: SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE POLICY - UNKNOWN INPUTS REMAIN UNKNOWN")
c.drawString(left, 15, f"Code: {SUBMISSION['repository_url']}  |  Private reviewer access required")
c.showPage()
c.save()
print(json.dumps({"status": "ok", "output": str(OUTPUT), "pages": 1}, indent=2))
