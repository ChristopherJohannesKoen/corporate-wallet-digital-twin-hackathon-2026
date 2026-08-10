from __future__ import annotations

import json
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from jupyter_client.kernelspec import KernelSpecManager


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "01_wallet_twin_demo.ipynb"
HTML_OUTPUT = ROOT / "output" / "notebook" / "01_wallet_twin_demo.html"


def code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(source.strip())


def build() -> nbf.NotebookNode:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {
            "display_name": "Corporate Wallet V3",
            "language": "python",
            "name": "wallet-twin-v3",
        },
        "language_info": {"name": "python", "version": "3"},
        "submission": {
            "team": "Corporate Wallet Digital Twin",
            "member": "Christopher Koen",
            "solution_version": "V3.0",
            "as_of": "2026-06-30",
        },
    }
    notebook["cells"] = [
        markdown(
            """
# Corporate Wallet Digital Twin V3 — executed judging notebook

**Team:** Corporate Wallet Digital Twin

**Member:** Christopher Koen

**Snapshot:** 30 June 2026

**Build:** V3.0 / 10 August 2026

V3 reconstructs the latent corporate financial system from one bank's partial observations, then optimizes decisions and evidence acquisition under uncertainty.

> **Claim boundary:** Syn Bank activity is simulated; public facts are E1; priors and calibration panels are representative. Reconstructed external flows are **scenarios, not measured competitor transactions**. Commercial values are not bank-approved and causal incremental value is withheld.
"""
        ),
        code(
            """
from pathlib import Path
import json, sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

ROOT = Path.cwd()
if not (ROOT / 'src').exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))

from wallet_twin_v3.repository import repository

v3 = json.loads((ROOT / 'dashboard/app/data/v3-fixture.json').read_text(encoding='utf-8'))
v2 = json.loads((ROOT / 'dashboard/app/data/shadow-fixture.json').read_text(encoding='utf-8'))
print(f"Loaded {len(repository.opportunities)} live V3 model objects and {len(v3['opportunities'])} exported contract records.")
print(v3['metadata']['watermark'])
"""
        ),
        markdown(
            """
## 1. Deterministic V3 validation boundary

This table verifies the implemented mechanics. It does not substitute for E3 calibration, approved bank economics or qualified RM outcomes.
"""
        ),
        code(
            """
validation = pd.DataFrame([
    ('Client-product opportunities', v3['validation']['opportunities'], 'replayed'),
    ('Portfolio clients', v3['validation']['clients'], 'replayed'),
    ('Shadow-wallet edges', v3['validation']['shadow_flow_edges'], 'mass balanced'),
    ('Maximum balance error (ZAR)', v3['validation']['max_mass_balance_error_zar'], 'must equal zero'),
    ('PU labelled positives', v3['validation']['pu_labelled_positives'], 'positive–unlabelled'),
    ('Change-point series', v3['validation']['change_point_series'], 'representative replay'),
    ('Selected RM actions', v3['validation']['rm_actions_selected'], 'capacity respected'),
    ('Selected evidence requests', v3['validation']['positive_net_voi_requests'], 'all net-positive'),
    ('Measured competitor-share claims', v3['validation']['measured_competitor_share_claims'], 'must equal zero'),
    ('Causal-value claims', v3['validation']['causal_value_claims'], 'must equal zero'),
], columns=['check', 'value', 'interpretation'])
display(validation)
assert v3['validation']['max_mass_balance_error_zar'] == 0
assert v3['validation']['anonymous_provider_nodes_only']
assert v3['validation']['measured_competitor_share_claims'] == 0
assert v3['validation']['causal_value_claims'] == 0
"""
        ),
        markdown(
            """
## 2. Shadow Wallet reconstruction — Glencore Trade Finance

The posterior wallet interval constrains total mass. Entropy-regularised Sinkhorn transport distributes the latent component over corridor priors and anonymous provider nodes. The equality below is exact by construction, while every external edge remains `SCENARIO` / `RECONSTRUCTED_NOT_MEASURED`.
"""
        ),
        code(
            """
glencore = next(o for o in v3['opportunities'] if o['opportunity_id'] == 'E02-trade-finance')
s = glencore['shadow_wallet']
shadow_summary = pd.DataFrame({
    'metric': ['Observed Syn Bank flow', 'Latent external wallet', 'Total wallet', 'Scenario bank share', 'Network entropy'],
    'lower': [s['observed_bank_flow'], s['latent_external_wallet']['lower'], s['total_wallet']['lower'], s['bank_share']['lower'], np.nan],
    'median': [s['observed_bank_flow'], s['latent_external_wallet']['median'], s['total_wallet']['median'], s['bank_share']['median'], s['normalized_entropy']],
    'upper': [s['observed_bank_flow'], s['latent_external_wallet']['upper'], s['total_wallet']['upper'], s['bank_share']['upper'], np.nan],
})
display(shadow_summary)

balance_error = abs(s['total_wallet']['median'] - s['observed_bank_flow'] - s['latent_external_wallet']['median'])
print(f"Median mass-balance error: R{balance_error:,.2f}")
print(f"Measurement status: {s['measurement_status']} | Draws: {s['ensemble_draws']}")
assert balance_error < 0.01
assert all(not flow['observed_by_bank'] for flow in s['flows'])
assert all(flow['provider_node'].startswith('External provider ') for flow in s['flows'])
"""
        ),
        code(
            """
flow_df = pd.DataFrame(s['flows'])
flow_df['median_zar_bn'] = flow_df['amount'].map(lambda x: x['median'] / 1e9)
pivot = flow_df.pivot_table(index='corridor', columns='provider_node', values='median_zar_bn', aggfunc='sum')
pivot.plot(kind='barh', stacked=True, figsize=(9, 4.8), color=['#0B63E5', '#7658D6', '#E2951C'])
plt.title('Glencore Trade Finance — reconstructed external wallet (scenario median)')
plt.xlabel('ZAR billions')
plt.ylabel('Corridor prior')
plt.legend(title='Anonymous node', loc='lower right')
plt.tight_layout()
plt.show()
"""
        ),
        markdown(
            """
## 3. Positive–Unlabelled need and Bayesian change-points

The Elkan–Noto correction estimates product need when only selected positives are labelled. It retains the SCAR assumption and selection constant. Bayesian run-length filtering then surfaces timing shifts. A leakage alarm is a verification signal—not proof of a competitor transfer.
"""
        ),
        code(
            """
need_rows = [{
    'client': o['entity_name'], 'product': o['product'],
    'need_probability': o['need']['product_need_probability'],
    'labelled_positive': o['need']['positive_label_observed'],
    'selection_constant': o['need']['selection_constant'],
} for o in v3['opportunities']]
needs = pd.DataFrame(need_rows).sort_values(['need_probability','client'], ascending=[False, True])
display(needs.head(12))
print('SCAR assumptions:', '; '.join(glencore['need']['assumptions']))
"""
        ),
        code(
            """
leakage_rows = [{
    'client': o['entity_name'], 'product': o['product'],
    'alarm_probability': o['leakage']['alarm_probability'],
    'observed_decline': o['leakage']['observed_level_decline'],
    'recent_peak_cp': o['change_point']['recent_peak_probability'],
    'event_90d': o['change_point']['probability_90d'],
    'status': o['leakage']['measurement_status'],
} for o in v3['opportunities']]
leakage = pd.DataFrame(leakage_rows).sort_values('alarm_probability', ascending=False)
display(leakage.head(12))
assert leakage['status'].eq('MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE').all()
"""
        ),
        markdown(
            """
## 4. Robust RM portfolio — scarce attention is the decision

The optimizer uses 512 scenario draws, expected scenario value and lower-tail CVaR. It selects at most one action per client, four per product and four per sector. Causal incremental value is withheld.
"""
        ),
        code(
            """
portfolio = v3['action_portfolio']
actions = pd.DataFrame(portfolio['selected_actions'])
display(actions[['entity_name','product','need_probability','leakage_probability','expected_scenario_value_zar','downside_cvar_zar','robust_score']])
print(f"Expected scenario value: R{portfolio['expected_scenario_value_zar']:,.0f}")
print(f"Downside portfolio CVaR: R{portfolio['downside_cvar_zar']:,.0f}")
print('Product counts:', portfolio['product_counts'])
print('Causal status:', portfolio['causal_status'])
assert len(actions) == portfolio['capacity'] == 12
assert actions['entity_id'].nunique() == len(actions)
assert max(portfolio['product_counts'].values()) <= 4
assert max(portfolio['sector_counts'].values()) <= 4
"""
        ),
        code(
            """
plot_actions = actions.sort_values('expected_scenario_value_zar')
plt.figure(figsize=(9, 5.5))
plt.barh(plot_actions['entity_name'] + ' — ' + plot_actions['product'], plot_actions['expected_scenario_value_zar']/1e6, color='#0B63E5', label='Expected scenario')
plt.scatter(plot_actions['downside_cvar_zar']/1e6, range(len(plot_actions)), color='#E2951C', label='Downside CVaR', zorder=3)
plt.xlabel('Representative scenario value (ZAR millions)')
plt.title('V3 capacity-constrained RM action portfolio')
plt.legend()
plt.tight_layout()
plt.show()
"""
        ),
        markdown(
            """
## 5. Decision-Directed evidence acquisition

Evidence is queued only when expected portfolio-decision value exceeds acquisition cost and latency. `autonomous_external_retrieval=False` is a release invariant.
"""
        ),
        code(
            """
plan = v3['evidence_acquisition']
voi = pd.DataFrame(plan['selected'])
display(voi[['entity_id','product','evidence_type','expected_rank_flip_probability','expected_interval_width_reduction','net_value_of_information_zar','required_approval']])
print(f"Selected net VOI: R{voi['net_value_of_information_zar'].sum():,.0f}")
print('Autonomous external retrieval:', plan['autonomous_external_retrieval'])
assert not plan['autonomous_external_retrieval']
assert (voi['net_value_of_information_zar'] > 0).all()
"""
        ),
        markdown(
            """
## 6. Rate/prior sensitivity — does Trade Finance remain dominant?

The frozen 3×3 benchmark is preserved for continuity and the 10,000-draw Latin-hypercube experiment reports rank and portfolio composition separately. Trade Finance remains first-ranked, but does not constitute a majority of the top ten or of the V3 action portfolio.
"""
        ),
        code(
            """
sens = v2['sensitivity']
product_summary = pd.DataFrame(sens['product_summary']).T.reset_index(names='product')
product_summary['median_economics_zar'] = product_summary['absolute_economics'].map(lambda x: x['p50'])
display(product_summary[['product','first_rank_frequency','mean_top10_share','majority_dominance_frequency','median_economics_zar']])
trade = sens['product_summary']['Trade finance']
print(f"Trade Finance first-rank frequency: {trade['first_rank_frequency']:.1%}")
print(f"Trade Finance mean top-10 share: {trade['mean_top10_share']:.1%}")
print(f"Trade Finance majority-dominance frequency: {trade['majority_dominance_frequency']:.1%}")
print(f"V3 action-portfolio share: {portfolio['product_counts']['Trade finance'] / portfolio['capacity']:.1%}")
assert trade['first_rank_frequency'] == 1.0
assert trade['majority_dominance_frequency'] == 0.0
"""
        ),
        markdown(
            """
## 7. Evidence-cited brief — BHP Trade Finance

The deterministic claim compiler is the operational fallback and the only input allowed to a provider gateway. It separates observed, public, modelled and missing-evidence claims and prohibits measured-share, optimal-share and causal-uplift language.
"""
        ),
        code(
            """
brief = repository.brief('E01-trade-finance', repository.as_of)
display(Markdown(f"### {brief['headline']}\\n\\n**Decision:** {brief['decision']}"))
print(json.dumps(brief, indent=2, default=str))
assert brief['llm_contract']['external_tools'] is False
assert brief['llm_contract']['autonomous_action'] is False
assert 'measured competitor share' in brief['prohibited_phrases']
"""
        ),
        markdown(
            """
## 8. Release conclusion

**Implemented and demo-ready:** entropy-constrained Shadow Wallet reconstruction; PU product-need model; Bayesian change-point/leakage signal; CVaR-aware RM portfolio; decision-directed evidence queue; governed claim compiler; V3 APIs; ABAC-protected decision lab; reproducible fixtures and tests.

**External gates that code cannot manufacture:** representative E3 multibank observations, approved pricing/FTP/capital/risk/cost inputs, bank AWS/Databricks/SSO/Unity Catalog/SIEM, approved live-provider evaluation, and supervised RM pilot/randomized trial.

The deployable demo is therefore a **client-facing representative decision lab**, not a bank-production or causal-value claim.
"""
        ),
    ]
    return notebook


def main() -> None:
    kernel_dir = ROOT / "tmp" / "v3-notebook-kernel"
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "kernel.json").write_text(
        json.dumps(
            {
                "argv": [
                    sys.executable,
                    "-m",
                    "ipykernel_launcher",
                    "-f",
                    "{connection_file}",
                ],
                "display_name": "Corporate Wallet V3",
                "language": "python",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    KernelSpecManager().install_kernel_spec(
        str(kernel_dir),
        kernel_name="wallet-twin-v3",
        prefix=sys.prefix,
    )
    notebook = build()
    client = NotebookClient(
        notebook,
        timeout=300,
        kernel_name="wallet-twin-v3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    executed = client.execute()
    executed.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(executed, OUTPUT)
    HTML_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    html, _ = HTMLExporter().from_notebook_node(executed)
    HTML_OUTPUT.write_text(html, encoding="utf-8")
    cells = len(executed.cells)
    outputs = sum(
        len(cell.get("outputs", []))
        for cell in executed.cells
        if cell.cell_type == "code"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "html_output": str(HTML_OUTPUT),
                "cells": cells,
                "stored_outputs": outputs,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
