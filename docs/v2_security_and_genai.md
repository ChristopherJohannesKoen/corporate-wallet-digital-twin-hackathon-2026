# Security, privacy and GenAI controls

Authorization is deny by default. The local harness supplies two explicit identity doubles for positive and negative tests, while any non-fixture deployment requires bank identity. Client, region, product, environment and sensitive-economics attributes are evaluated before access; policy decisions are evented.

The provider gateway supports OpenAI Responses, Anthropic Messages and Google GenAI behind one contract. A provider is callable only when all three of these controls are present: an explicit approval flag, a pinned model snapshot and a credential supplied at runtime. `GENAI_PROVIDER` defaults to `deterministic`. Provider status returns booleans only and never credential values.

Provider behavior:

- OpenAI uses schema-constrained Responses parsing, `store: false`, no tools and no autonomous action.
- Anthropic uses schema-constrained Messages parsing.
- Google uses JSON-schema constrained generation.
- Every provider response passes the deterministic whole-narrative number/evidence claim compiler; any error falls back to deterministic narration.
- A payload guard rejects prompt injection, secret-like content, oversized requests and excessive evidence before a provider call.
- Per-provider circuit breakers stop repeated failing calls and preserve the deterministic operational path.
- Audit records retain only hashes, artifact versions, provider/mode and reason codes; prompts and payloads are not retained.

No live credential is stored in this repository or deployment fixture. Credentials pasted into a conversation must be revoked and rotated before use. Rotated values belong in an approved secret manager or local process environment, never `.env.example`, source control, fixtures, logs or CI output.

The evaluation estate is:

<!-- BEGIN GENERATED: governed-checks -->

169 evidence-grounded governed checks (36 sealed/dev/training golden cases, 82 evidence-register replays and 51 page-grounded fact replays), plus a 640-case deterministic validator stress suite — 809 checks in total, of which 79% exercise validators and abstention mechanics with no model call. The two figures measure different things and are reported separately for that reason.
<!-- END GENERATED: governed-checks -->

It covers OCR ambiguity, complex tables, scale, sign, currency, restatement, conflicts, missing fields, future data and prompt injection. Run it with:

```powershell
python scripts/run_genai_evals.py
```

The deterministic baseline passes the sealed synthetic text split with zero prompt-injection successes, and all 51 expanded facts match their official cited pages. External-provider results are explicitly `CONFIGURABLE_NOT_EXECUTED`; production release remains false until bank approval, approved live-provider evaluation and independent finance-SME adjudication exist.
