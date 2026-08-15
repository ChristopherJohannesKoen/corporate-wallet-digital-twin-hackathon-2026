"""Build and execute the canonical V3.2.0 judging notebook.

The notebook has two modes.  Private evaluator mode reads ``SYNBANK_DATA_ZIP``
or the local confidential challenge archive; public mirror mode uses the
independently generated aggregate fixture and never contains supplied rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import nbformat as nbf
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
from nbconvert import HTMLExporter


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "01_wallet_twin_demo.ipynb"
HTML_OUTPUT = ROOT / "output" / "notebook" / "01_wallet_twin_demo.html"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def build():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Corporate Wallet V3.2.0", "language": "python", "name": "wallet-twin-v320"},
        "language_info": {"name": "python", "version": "3"},
        "submission": {
            "team": "Corporate Wallet Digital Twin",
            "member": "Christopher Koen",
            "solution_version": "V3.2.0",
            "as_of": "2026-06-30",
            "confidential_rows_embedded": False,
        },
    }
    nb.cells = [
        markdown("""
# Corporate Wallet Digital Twin V3.2.0 — executed judging notebook

**Team:** Corporate Wallet Digital Twin  
**Member:** Christopher Koen  
**Point-in-time snapshot:** 30 June 2026

This notebook proves the hackathon chain end to end:

`Syn Bank activity + approved public evidence → wallet/share intervals → contestable gap → 20 × 5 heatmap → governed conversation → grounded brief`

> **Claim boundary.** The supplied Syn Bank data is simulated and confidential. Public facts are E1 candidates; only 31 finance-SME-approved facts activate 15 anchors. The other 51 facts are developer-verified candidates and excluded from inference. Competitor share is not measured, economics are representative scenarios, and causal value is withheld.
"""),
        code("""
from pathlib import Path
import hashlib, json, os, sys, zipfile
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

ROOT = Path.cwd()
if not (ROOT / 'src').exists(): ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))
from wallet_twin_v2.offline_lab import _aggregate_historical
from wallet_twin_v2.repository import repository as v2
from wallet_twin_v31.repository import repository as v31

configured = os.getenv('SYNBANK_DATA_ZIP')
private_default = ROOT / 'ref' / 'Data Sets' / 'Data.zip'
archive = Path(configured).expanduser().resolve() if configured else private_default
mode = 'PRIVATE_EVALUATOR' if archive.exists() else 'PUBLIC_MIRROR'
print('Mode:', mode)
print('Version:', v31.metadata['version'], '| as of:', v31.as_of)
print('Bank production:', v31.release['bank_production_status'])
"""),
        markdown("## 1. Source archive, hash, member list and data-quality boundary"),
        code("""
if mode == 'PRIVATE_EVALUATOR':
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as zf:
        members = [{'member': item.filename, 'compressed_bytes': item.compress_size, 'bytes': item.file_size} for item in zf.infolist()]
    display(pd.DataFrame(members))
    print('Data.zip SHA-256:', archive_hash)
    monthly, raw_counts = _aggregate_historical(archive)
else:
    archive_hash = 'PUBLIC_MIRROR_INDEPENDENTLY_GENERATED_FIXTURE'
    cells = v31.wallet_portfolio(v31.as_of).cells
    monthly = pd.DataFrame([{
        'entity_id': cell.entity_id, 'sector': cell.sector, 'month': '2026-06',
        'product': cell.product, 'amount_zar': float(cell.observed_activity.normalized_amount)
    } for cell in cells])
    raw_counts = {'independently_generated_aggregate_rows': len(monthly)}
print('Raw/fixture row counts:', raw_counts)
print('Monthly aggregate rows:', len(monthly), '| clients:', monthly.entity_id.nunique(), '| products:', monthly['product'].nunique())
assert monthly.entity_id.nunique() == 20 and monthly['product'].nunique() == 5
"""),
        markdown("""
## 2. Product transformation contract

The private pipeline streams the archive and maps:

- inbound transaction legs → **Collections**;
- outbound transaction legs → **Payments**;
- absolute net monthly cash movement → **Liquidity-flow proxy**;
- cross-border payment value → **FX exposure proxy**;
- trade instruments → **Trade Finance**.

FX is not executed FX revenue and Liquidity is not a deposit stock. Heterogeneous product quantities are never summed as one “banking spend” number.
"""),
        code("""
display(monthly.groupby(['entity_id','product'], as_index=False).amount_zar.sum().head(15))
schemas = {column: str(dtype) for column, dtype in monthly.dtypes.items()}
quality = {
    'null_entity_ids': int(monthly.entity_id.isna().sum()),
    'negative_amounts': int((monthly.amount_zar < 0).sum()),
    'duplicate_month_client_product': int(monthly.duplicated(['entity_id','month','product']).sum()),
}
display(pd.Series(schemas, name='dtype').to_frame())
display(pd.Series(quality, name='count').to_frame())
assert quality['null_entity_ids'] == 0 and quality['negative_amounts'] == 0
"""),
        markdown("## 3. Approval-authoritative public anchors"),
        code("""
wallet = v31.wallet_portfolio(v31.as_of)
approval = pd.DataFrame([{
    'opportunity': cell.opportunity_id, 'client': cell.entity_name, 'product': cell.product,
    'tier': cell.evidence_tier.value, 'activation': cell.anchor_activation,
    'approval_state': cell.approval_state, 'active_facts': len(cell.active_fact_ids),
    'pending_facts_excluded': len(cell.pending_fact_ids),
} for cell in wallet.cells])
display(approval.groupby(['tier','activation','approval_state']).size().rename('cells').to_frame())
print('Source estate:', wallet.approved_source_facts, 'approved +', wallet.pending_source_facts, 'pending = 82')
assert len(approval) == 100
assert (approval.activation == 'ACTIVATED').sum() == 15
assert (approval.tier == 'E0').sum() == 85
assert not any(set(cell.active_fact_ids) & set(cell.pending_fact_ids) for cell in wallet.cells)
"""),
        markdown("## 4. Identification and posterior equations"),
        code("""
equations = pd.DataFrame([{
    'client': cell.entity_name, 'product': cell.product,
    'A_observed': float(cell.observed_activity.normalized_amount),
    'T_bound_low': cell.identification_bounds.lower, 'T_bound_high': cell.identification_bounds.upper,
    'T_p10': cell.posterior_wallet.lower, 'T_p50': cell.posterior_wallet.median, 'T_p90': cell.posterior_wallet.upper,
    'q_p10': cell.share_interval.lower, 'q_p50': cell.share_interval.median, 'q_p90': cell.share_interval.upper,
    'q_star': cell.target_share_scenario,
    'G_p50': cell.contestable_activity.median,
    'scenario_contribution': cell.scenario_contribution.median if cell.scenario_contribution else 0.0,
} for cell in wallet.cells])
equations['identity_error'] = abs(equations.A_observed / equations.T_p50 - equations.q_p50)
equations['gap_error'] = abs(equations.G_p50 - np.maximum(equations.q_star * equations.T_p50 - equations.A_observed, 0))
display(equations.head())
print('Max A=qT median-quantile error:', equations.identity_error.max())
print('Max G equation error (ZAR):', equations.gap_error.max())
assert (equations.T_p10 >= equations.A_observed).all()
assert equations.identity_error.max() < 2e-5
assert equations.gap_error.max() < 0.02
"""),
        markdown("## 5. Complete 20 × 5 contestable contribution heatmap"),
        code("""
heat = equations.pivot(index='client', columns='product', values='scenario_contribution')
heat = heat[['Collections','Payments','Liquidity','Cross-border FX','Trade finance']]
fig, ax = plt.subplots(figsize=(11,7))
image = ax.imshow(np.log1p(heat.values), cmap='Blues', aspect='auto')
ax.set_xticks(range(5), ['Collections','Payments','Liquidity flow','FX exposure','Trade finance'], rotation=20, ha='right')
ax.set_yticks(range(20), heat.index)
ax.set_title('20 × 5 contestable scenario contribution — log colour scale')
fig.colorbar(image, ax=ax, label='log(1 + representative contribution ZAR)')
plt.tight_layout(); plt.show()
assert heat.shape == (20,5) and heat.notna().all().all()
"""),
        markdown("## 6. BHP forensic drill-down: A, T, q, q*, G and cited evidence"),
        code("""
bhp_cells = [cell for cell in wallet.cells if cell.entity_id == 'E01']
bhp = max(bhp_cells, key=lambda cell: cell.scenario_contribution.median if cell.scenario_contribution else 0)
detail = v31.wallet_opportunity(bhp.opportunity_id, v31.as_of)
display(pd.DataFrame([
    ['A — observed', detail.explanation['A']['value'], 'OBSERVED'],
    ['T — P10', detail.explanation['T']['p10'], 'POSTERIOR'],
    ['T — P50', detail.explanation['T']['p50'], 'POSTERIOR'],
    ['T — P90', detail.explanation['T']['p90'], 'POSTERIOR'],
    ['q — P50', detail.explanation['q']['p50'], 'POSTERIOR'],
    ['q*', detail.explanation['q_star']['value'], 'SCENARIO'],
    ['G — P50', detail.explanation['G']['p50'], 'SCENARIO'],
], columns=['quantity','value','claim_class']))
facts = pd.DataFrame(detail.supporting_facts)
display(facts[['fact_id','concept','value','currency','unit','source_title','page','source_url','qa_and_approval_state']])
assert all(facts.qa_and_approval_state == 'APPROVED_ACTIVE')
"""),
        markdown("## 7. E1 pooling sensitivity and Trade Finance dominance"),
        code("""
sensitivity = json.loads((ROOT / 'outputs/v2_validation/measurement_policy_sensitivity.json').read_text())
arms = pd.DataFrame([
    {
        'e1_weight': float(weight),
        'policy_version': arm['policy_version'],
        'top_opportunity': arm['ranking'][0],
        'activated_cells': arm['activated_cells'],
        'mean_activated_interval_width': np.mean([cell['posterior_wallet_interval_width'] for cell in arm['cells'] if cell['activated']]),
    }
    for weight, arm in sensitivity['arms'].items()
])
display(arms)
trade = json.loads((ROOT / 'dashboard/app/data/shadow-fixture.json').read_text())['sensitivity']['product_summary']['Trade finance']
display(pd.Series(trade, name='Trade finance sensitivity').to_frame())
print('Conclusion:', sensitivity['headline'])
assert set(arms.e1_weight) == {0.2,0.35,0.5}
"""),
        markdown("## 8. Wallet gap → stakeholder, problem, solution and timing"),
        code("""
action = detail.decision_twin_action
display(pd.Series(action, name='BHP action layer').to_frame())
conversation = v31.conversation(action['conversation_id'], v31.as_of)
print('30/60/90-day:', conversation.engagement_window.probability_30d, conversation.engagement_window.probability_60d, conversation.engagement_window.probability_90d)
print('Permitted action:', conversation.action.value)
assert conversation.action.value == 'DISCOVERY'
"""),
        markdown("## 9. Eight-conversation plan and active-learning loop"),
        code("""
plan = pd.DataFrame([entry.model_dump(mode='json') for entry in v31.plan.entries])
display(plan[['rank','entity_name','stakeholder_role','problem_label','solution_label','client_value_median','bank_value_median','selection_stability','action']])
question = conversation.next_best_question
print('Highest positive-net-VOI question:', question.question_text)
print('Net VOI:', question.net_voi_zar, '| common draws:', question.scenario_draws)
from wallet_twin_v31.questions import ClientAnswerWorkflow
workflow = ClientAnswerWorkflow(v31.as_of)
answer = workflow.submit(answer_id='notebook-answer', question=question, answer_state_id=question.answer_states[0].state_id, respondent_role=conversation.stakeholder.primary_role, respondent_type='CLIENT', consent_reference='demo-consent', scope='relationship discovery', source='demo meeting note')
print('Answer state:', answer.approval_status, '| changes approved snapshot:', answer.resulting_claim_id is not None)
assert len(plan) == 8 and answer.approval_status.value == 'PENDING_REVIEW'
"""),
        markdown("## 10. Grounded briefs and comparative external-provider evaluation"),
        code("""
brief = v31.brief(conversation.conversation_id, v31.as_of)
brief_markdown = '### {}\\n\\n**WHY** {}\\n\\n**HOW** {}\\n\\n**WHAT** {}'.format(brief.headline, brief.why, brief.how, brief.what)
display(Markdown(brief_markdown))
truth = json.loads((ROOT / 'data/v2/submission_truth_v3.2.0.json').read_text())
comparison = truth['genai']
provider_rows = pd.DataFrame([
    {
        'client': item['entity_name'], 'provider': item['provider'],
        'model': item['canonical_model_id'], 'status': item['acceptance_status'],
        'schema': item['validation_metrics']['schema_compliance'],
        'numbers': item['validation_metrics']['numeric_preservation'],
        'citations': item['validation_metrics']['citation_precision'],
        'unsupported_critical': item['validation_metrics']['unsupported_critical_claims'],
    }
    for item in comparison['showcase_briefs'].values()
])
display(provider_rows)
for item in comparison['showcase_briefs'].values():
    narrative = item['accepted_narrative']
    display(Markdown('### {} / {}\\n\\n{}\\n\\n**Next action:** {}'.format(
        item['provider'].title(), item['canonical_model_id'], narrative['headline'], narrative['next_action']
    )))
print('Accepted provider outputs:', comparison['accepted_runs'], 'of', comparison['target_runs'], '| gate:', comparison['submission_gate_passed'])
print('One output was blocked by the claim compiler and retained its deterministic fallback.')
print('This is hackathon external-provider evaluation, not bank-authorized LIVE_GENAI. Fresh credentials are required only to rerun it.')
assert comparison['accepted_runs'] == 8 and comparison['blocked_runs'] == 1
assert comparison['submission_gate_passed'] is True
"""),
        markdown("## 11. Promotion Readiness Twin: real evidence and rehearsal evidence never mix"),
        code("""
promotion = json.loads((ROOT / 'dashboard/app/data/promotion-fixture.json').read_text())
summary = promotion['summary']
display(pd.DataFrame([
    ['Current real state', summary['real_state']],
    ['Highest rehearsed state', summary['rehearsed_state']],
    ['Promotion Machinery Readiness', f"{summary['promotion_machinery_readiness']:.0%}"],
    ['Bank Evidence Readiness', f"{summary['bank_evidence_readiness']:.0%}"],
    ['Bank shadow authorized', summary['bank_shadow_authorized']],
    ['Bank production', summary['bank_production_status']],
], columns=['control','value']))
gates = pd.DataFrame([
    {
        'transition': transition['transition_id'], 'gate': gate['gate_id'],
        'severity': gate['severity'], 'real': gate['real_outcome'],
        'rehearsal': gate['rehearsal_outcome'], 'mode': gate['evidence_mode'],
        'signed': gate['signature_status'],
    }
    for transition in promotion['transitions'] for gate in transition['gates']
])
display(gates.groupby(['real','rehearsal','mode']).size().rename('gates').to_frame())
print('Gate catalogue:', len(gates), 'gates across', len(promotion['transitions']), 'transitions')
assert len(gates) == 30
assert summary['promotion_machinery_readiness'] == 1.0
assert summary['bank_evidence_readiness'] == 0.0
assert summary['bank_shadow_authorized'] is False
"""),
        markdown("## 12. Synthetic E3 planning and accelerated shadow failure injection"),
        code("""
labs = json.loads((ROOT / 'outputs/v32/v32_simulation_laboratories.json').read_text())
e3_plan = labs['e3_sample_size_readiness']
plan_rows = pd.DataFrame(e3_plan['sweep'])
display(plan_rows[['n','replications','coverage_success_rate','crps_success_rate','subgroup_success_rate','all_criteria_wilson_lower','all_criteria_wilson_upper']])
print('E3 planning recommendation:', e3_plan['determination'], e3_plan['recommended_n'])
print('Evidence mode:', e3_plan['evidence_mode'], '— cannot enable measured share')

clock = promotion['clock']
display(pd.Series(clock, name='Accelerated shadow rehearsal').to_frame())
assert clock['rehearsal_days_elapsed'] == 47
assert clock['consecutive_clean_rehearsal_days'] == 30
assert clock['elapsed_bank_shadow_days'] == 0
assert 'RECONCILIATION' in clock['last_reset_reason']
"""),
        markdown("## 13. Consequence-level capability permissions"),
        code("""
capabilities = pd.DataFrame(promotion['capabilities'])
display(capabilities[['capability','granted','refusal_reason']])
required = {'DISCOVERY_CONVERSATION','POSTERIOR_WALLET','MEASURED_SHARE','SCENARIO_ECONOMICS','PRODUCT_PROPOSAL','LIVE_GENAI','CAUSAL_VALUE'}
assert required.issubset(set(capabilities.capability))
print('A rehearsed state never grants a real capability; each permission uses real state and real evidence prerequisites.')
"""),
        markdown("## 14. Validation hierarchy and release conclusion"),
        code("""
hierarchy = pd.DataFrame([
    ['Mechanical', 'contracts, equations, point-in-time, authorization, reproducibility', 'PASSED'],
    ['Known truth', 'synthetic calibration and deterministic golden set', 'PASSED FOR MECHANICS'],
    ['Predictive', 'E3 wallet/share panel and qualified RM outcomes', 'OPEN'],
    ['External', 'approved economics, live providers, bank controls and pilot', 'OPEN'],
], columns=['level','evidence','status'])
display(hierarchy)
print('Hackathon software state: HACKATHON_SUBMISSION_READY after final artifact/CI gates')
print('Bank production state:', v31.release['bank_production_status'])
print('Promotion state:', summary['real_state'])
print('Rehearsal claim: SHADOW_PROMOTION_REHEARSAL_PASSED')
assert v31.validation['measured_competitor_share_claims'] == 0
assert v31.validation['causal_value_claims'] == 0
assert v31.release['bank_production_status'] == 'NOT_PROMOTABLE'
"""),
        markdown("""
## Limitations

- 85 of 100 wallet cells are prior-led because pending public facts cannot activate anchors.
- E1 accounting proxies do not measure competitor transactions; E3 is required for a measured-share label.
- Pricing, FTP, capital, risk, cost-to-win and hurdle rates are representative, not bank-approved.
- Timing is a transparent baseline, not a qualified-RM-outcome calibrated hazard model.
- Live provider evaluation remains incomplete until fresh rotated credentials and explicit acknowledgement are supplied.
- No RM pilot or randomized trial has established causal impact.
- The 30 clean shadow days are virtual rehearsal days; elapsed bank shadow days remain zero.
- PMR 100% proves the promotion machinery and its refusal paths execute. BER 0% proves no bank evidence has been substituted by simulation.

These limitations block bank promotion but do not invalidate the reproducible hackathon demonstration.
"""),
    ]
    return nb


def main():
    kernel_dir = ROOT / "tmp" / "v320-notebook-kernel"
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Corporate Wallet V3.2.0", "language": "python",
    }, indent=2), encoding="utf-8")
    KernelSpecManager().install_kernel_spec(str(kernel_dir), kernel_name="wallet-twin-v320", prefix=sys.prefix)
    executed = NotebookClient(build(), timeout=600, kernel_name="wallet-twin-v320", resources={"metadata": {"path": str(ROOT)}}).execute()
    executed.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(executed, OUTPUT)
    HTML_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    html, _ = HTMLExporter().from_notebook_node(executed)
    HTML_OUTPUT.write_text(html, encoding="utf-8")
    result = {
        "output": str(OUTPUT), "html_output": str(HTML_OUTPUT),
        "cells": len(executed.cells),
        "stored_outputs": sum(len(cell.get("outputs", [])) for cell in executed.cells if cell.cell_type == "code"),
        "errors": sum(any(output.output_type == "error" for output in cell.get("outputs", [])) for cell in executed.cells if cell.cell_type == "code"),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
