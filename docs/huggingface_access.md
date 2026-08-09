# Secure Hugging Face access

Public Hugging Face discovery is already authenticated locally with a
fine-grained token. No token needs to be sent in chat.

For private or gated datasets:

1. Create a fine-grained **read-only** token at
   `https://huggingface.co/settings/tokens`.
2. Restrict it to the named dataset repositories; do not grant model, Space,
   endpoint, organisation administration or write permissions unless a separate
   workflow specifically requires them.
3. In the local terminal, run `hf auth login` and paste the token only into that
   interactive prompt. Do not put it in source code, a command argument, a chat
   message, a notebook or a committed `.env` file.
4. Confirm the identity with `hf auth whoami`. Do not print `HF_TOKEN`.
5. For EKS or a Hugging Face Job, place the token in the bank secret manager and
   inject it as `HF_TOKEN` at runtime. Use a separate token for uploads.

Before a private dataset is admitted, add its owner, exact revision SHA,
licence/permissible-use basis, row count, PII classification, purpose and
production eligibility to `data/v2/external_dataset_registry.json`. Downloaded
snapshots require a SHA-256. Private data is never uploaded elsewhere by this
project without an explicit approved destination and separate authority.

