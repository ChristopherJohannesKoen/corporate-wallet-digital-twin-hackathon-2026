# Grounded GenAI design

> **Archived V1 design note.** The current V3 implementation uses the governed V2 provider gateway plus V3 decision-directed evidence acquisition and closed claim-pack compilation, documented in [`Corporate_Wallet_Digital_Twin_V3_Technical_Foundations.md`](Corporate_Wallet_Digital_Twin_V3_Technical_Foundations.md). Model names and enablement rules below are retained only as a V1 regression reference.

## Principle

The LLM is semantic; Python is numeric truth. The workflow does not ask a model to read millions of rows, compute wallet values, or infer missing public facts.

## Workflow

1. Python writes a structured client evidence pack containing the model version, as-of date, client state, product opportunities, provenance and claim policy.
2. Retrieval uses lexical BM25 with a source-quality rerank. An embedding retriever can be added later behind the same interface.
3. One orchestrator passes only the relevant evidence to the language model. There is no deep serial agent chain.
4. `prompts/banker_brief.md` defines the outcome, required sections, numeric-preservation rule, citations, inference labels, abstention and completion bar.
5. If an API key is absent, an equivalent deterministic brief is generated. This makes judging and testing reproducible.

## Optional OpenAI call

The implementation uses the Responses API with `gpt-5.6-sol`, low reasoning effort and medium text verbosity. The model choice is configurable through `OPENAI_MODEL`. The integration does not enable tool calling, persisted reasoning, programmatic tool calling, multi-agent beta or implicit external retrieval.

## Information security

Only supplied synthetic data and approved public facts may enter the evidence pack. Real confidential client information, personal data, credentials and internal restricted documents must not be sent to an external model without approved bank architecture, contracting, residency, retention and security controls.

## Evaluation rubric

- extraction accuracy for future public facts;
- numeric exact match / relative error;
- citation precision and recall;
- unsupported-claim rate;
- evidence faithfulness;
- actionability scored by bankers;
- correct abstention when required evidence is absent;
- latency P50/P95 and cost per accepted brief.

The golden set should include ordinary cases, conflicting evidence, missing facts, out-of-period facts and adversarial instructions embedded in source text.
