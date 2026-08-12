from __future__ import annotations

import json
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks/01_wallet_twin_demo.ipynb"
HTML_OUTPUT = ROOT / "output/notebook/01_wallet_twin_demo.html"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def build():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Corporate Wallet V3.1", "language": "python", "name": "wallet-twin-v31"},
        "language_info": {"name": "python", "version": "3"},
        "submission": {
            "team": "Corporate Wallet Digital Twin",
            "member": "Christopher Koen",
            "solution_version": "V3.1.0",
            "as_of": "2026-06-30",
        },
    }
    nb.cells = [
        markdown("""
# Corporate Wallet Digital Twin V3.1 - executed judging notebook

**Team:** Corporate Wallet Digital Twin  
**Member:** Christopher Koen  
**Snapshot:** 30 June 2026  
**Build:** 12 August 2026

The notebook reproduces the Corporate Banking Decision Twin: 20 twelve-component Business Twins, 320 client-solution estimates, the eight-conversation weekly plan, a BHP explanation path, dual value, funding-route intelligence and the reviewed value-of-information answer loop.

> **Claim boundary:** Syn Bank activity is simulated; public facts are E1; representative policies and E0 claims demonstrate mechanics. Competitor share is not measured, bank economics are not approved, feasibility remains unknown where bank systems are absent, and causal incremental value is withheld.
"""),
        code("""
from pathlib import Path
import json, sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

ROOT = Path.cwd()
if not (ROOT / 'src').exists(): ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))
from wallet_twin_v31.repository import repository

print(repository.metadata['title'])
print(repository.metadata['watermark'])
print('Bank production:', repository.release['bank_production_status'])
"""),
        markdown("## 1. Reproduce the governed V3.1 snapshot"),
        code("""
summary = pd.Series(repository.validation, name='value')
display(summary.loc[[
    'clients','business_twin_components','business_evidence_claims','business_evidence_gaps',
    'graph_nodes','graph_edges','problem_hypotheses','identified_problems',
    'solution_projections','available_solution_estimates','fail_closed_solution_estimates',
    'conversation_candidates','coverage_plan_size','voi_questions_evaluated','voi_questions_selected'
]].to_frame())
assert repository.validation['clients'] == 20
assert repository.validation['business_twin_components'] == 240
assert repository.validation['solution_projections'] == 320
assert repository.validation['coverage_plan_size'] == 8
assert repository.validation['coverage_solver_status'] == 'OPTIMAL'
"""),
        markdown("## 2. Twenty Business Model Twins and evidence completeness"),
        code("""
twin_rows = []
for entity_id, twin in repository.twins.items():
    coverage = repository.evidence_coverage['per_client'][entity_id]
    twin_rows.append({
        'client': twin.entity_name, 'sector': twin.sector, 'components': len(twin.components),
        'typed_claims': twin.claim_count, 'approved_claims': twin.approved_claim_count,
        'domains': twin.supported_domain_count, 'E1_approved': coverage['e1_approved_claims'],
        'gaps': len(twin.evidence_gaps), 'meets_15_E1_target': coverage['meets_e1_threshold'],
    })
twins = pd.DataFrame(twin_rows).sort_values('client')
display(twins)
assert (twins['components'] == 12).all()
assert (twins['typed_claims'] >= 15).all()
assert (twins['domains'] >= 9).all()
assert not twins['meets_15_E1_target'].any()
display(Markdown('**Open gate:** the real audited estate does not support 15 reviewed E1 claims per client. No fact has been invented to close it.'))
"""),
        markdown("## 3. All sixteen solutions across all twenty clients"),
        code("""
estimate_rows = []
for entity_id, estimates in repository.estimates.items():
    client = repository.twins[entity_id].entity_name
    for solution, estimate in estimates.items():
        estimate_rows.append({
            'client': client, 'solution': solution.value, 'status': 'AVAILABLE' if estimate.available else 'FAIL_CLOSED',
            'claim_class': estimate.claim_class.value, 'calibration': estimate.calibration_status,
            'reason_count': int(estimate.unavailable_reason is not None),
        })
estimates = pd.DataFrame(estimate_rows)
display(pd.crosstab(estimates['solution'], estimates['status']))
assert len(estimates) == 320
assert len(estimates['solution'].unique()) == 16
assert (estimates.groupby('client').size() == 16).all()
"""),
        markdown("## 4. Eight-conversation Pareto and CVaR weekly plan"),
        code("""
plan = pd.DataFrame([entry.model_dump(mode='json') for entry in repository.plan.entries])
display(plan[['rank','entity_name','stakeholder_role','problem_label','solution_label',
              'client_value_median','bank_value_median','selection_stability','action','eligibility']])
print('Solver:', repository.plan.solver_status, '| degraded fallback:', repository.plan.degraded_fallback)
print('Constraint report:', json.dumps(repository.plan.constraint_report, indent=2))
assert len(plan) == 8
assert repository.plan.solver_status == 'OPTIMAL'
assert not repository.plan.degraded_fallback
assert set(plan['action']) == {'DISCOVERY'}
"""),
        code("""
fig, ax = plt.subplots(figsize=(9,4.8))
colors = ['#0872df' if x != 'TRADE_FINANCE' else '#c47c0a' for x in plan['primary_solution']]
ax.barh(plan['entity_name'] + ' / ' + plan['solution_label'], plan['selection_stability'] * 100, color=colors)
ax.invert_yaxis(); ax.set_xlabel('Selection stability across scenario draws (%)')
ax.set_title('V3.1 weekly plan - stability, not opaque confidence')
ax.grid(axis='x', alpha=.2); plt.tight_layout(); plt.show()
"""),
        markdown("## 5. BHP explanation path and separated value"),
        code("""
bhp_entry = next(entry for entry in repository.plan.entries if entry.entity_name == 'BHP Group')
bhp = repository.conversation(bhp_entry.conversation_id, repository.as_of)
path = bhp.explanation_path
display(Markdown(f'''### {bhp.entity_name} - {bhp.problem.label}

**Stakeholder:** {bhp.stakeholder.primary_role.value}  
**Solution:** {bhp.solution_bundle.primary.value}  
**Path:** `Event -> Business impact -> Problem -> Stakeholder -> Solution -> Client value -> Bank value`  
**Why now:** {bhp.engagement_window.why_now}
'''))
print('Client value:', bhp.client_value.monetised_total)
print('Bank direct contribution:', bhp.bank_value.direct_contribution)
print('Three-year relationship scenario:', bhp.bank_value.relationship_value_3y)
print('Causal value:', bhp.bank_value.causal_incremental_value)
print('Evidence claims in path:', len({claim_id for step in path.steps for claim_id in step.evidence_claim_ids}))
assert bhp.bank_value.causal_incremental_value is None
assert bhp.risk_and_feasibility.permitted_action.value == 'DISCOVERY'
"""),
        markdown("## 6. Funding Route Intelligence"),
        code("""
routes = repository.funding_routes(bhp.entity_id, repository.as_of)
route_df = pd.DataFrame([row.model_dump(mode='json') for row in routes.routes])
display(route_df[['route','probability','score']])
print('Requirement:', routes.requirement)
print(routes.model_status)
assert abs(route_df['probability'].sum() - 1.0) < 1e-10
"""),
        markdown("## 7. Active Coverage Learning and reviewed answer boundary"),
        code("""
question = bhp.next_best_question
display(Markdown(f'''**Question:** {question.question_text}

Net VOI: **R{question.net_voi_zar:,.0f}** from {question.scenario_draws} common draws.  
Can change rank: {question.can_change_rank}; bundle: {question.can_change_bundle}; feasibility: {question.can_change_feasibility}; abstention: {question.can_change_abstention}.
'''))
assert question.net_voi_zar > 0
assert any([question.can_change_rank, question.can_change_bundle, question.can_change_feasibility, question.can_change_abstention])
"""),
        code("""
from wallet_twin_v31.questions import ClientAnswerWorkflow
workflow = ClientAnswerWorkflow(repository.as_of)
answer = workflow.submit(
    answer_id='notebook-bhp-answer-1',
    question=question,
    answer_state_id=question.answer_states[0].state_id,
    respondent_role=bhp.stakeholder.primary_role,
    respondent_type='CLIENT',
    consent_reference='demo-consent-record',
    scope='relationship discovery',
    source='Demonstration RM meeting note',
)
print('Submitted:', answer.approval_status, '| resulting claim:', answer.resulting_claim_id)
print('Approved snapshot unchanged:', repository.twins[bhp.entity_id].snapshot_id)
assert answer.approval_status.value == 'PENDING_REVIEW'
assert answer.resulting_claim_id is None
"""),
        markdown("## 8. Deterministic Why-How-What brief and release conclusion"),
        code("""
brief = repository.brief(bhp.conversation_id, repository.as_of)
display(Markdown(f'''### {brief.headline}

**WHY**  
{brief.why}

**HOW**  
{brief.how}

**WHAT**  
{brief.what}

**Primary question:** {brief.primary_question}
'''))
print('Compiler:', brief.compiler, '| provider:', brief.provider_used)
print('Prohibited claims:', brief.prohibited_claims)
assert brief.fallback_available
"""),
        code("""
release = repository.release
print('Client demo:', release['client_demo_status'])
print('Bank production:', release['bank_production_status'])
for gate in release['blocking_external_gates']:
    print(' -', gate)
assert release['bank_production_status'] == 'NOT_PROMOTABLE'
assert repository.validation['measured_competitor_share_claims'] == 0
assert repository.validation['causal_value_claims'] == 0
"""),
        markdown("""
## Reproduction conclusion

The executed notebook reproduces the complete V3.1 client-demo boundary from repository objects, not a manually prepared slide claim. It validates all 20 twins, all 320 solution estimates, the Pareto/CVaR weekly plan, BHP's explanation and dual value, funding-route probability coherence, a positive-net-VOI question and the pending-E2 review boundary.

Bank promotion remains `NOT_PROMOTABLE` until the external evidence, economics, infrastructure, provider, pilot, trial and clean-shadow gates are completed.
"""),
    ]
    return nb


def main():
    kernel_dir = ROOT / "tmp/v31-notebook-kernel"
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Corporate Wallet V3.1", "language": "python",
    }, indent=2), encoding="utf-8")
    KernelSpecManager().install_kernel_spec(str(kernel_dir), kernel_name="wallet-twin-v31", prefix=sys.prefix)
    notebook = build()
    executed = NotebookClient(notebook, timeout=300, kernel_name="wallet-twin-v31", resources={"metadata": {"path": str(ROOT)}}).execute()
    executed.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(executed, OUTPUT)
    HTML_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    html, _ = HTMLExporter().from_notebook_node(executed)
    HTML_OUTPUT.write_text(html, encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT), "html_output": str(HTML_OUTPUT),
        "cells": len(executed.cells),
        "stored_outputs": sum(len(cell.get('outputs', [])) for cell in executed.cells if cell.cell_type == 'code'),
    }, indent=2))


if __name__ == "__main__":
    main()
