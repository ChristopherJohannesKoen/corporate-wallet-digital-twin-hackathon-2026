# Frozen V1 boundary

`src/wallet_twin`, the original documents and `outputs` remain read-only
regression evidence for V2. V2 code imports only the frozen expected-result
fixture through `wallet_twin_v2.fixtures`; it never imports or executes the V1
runtime. Archive or remove V1 only after the bank-managed repository has retained
its signed fixture manifest and V2 baseline tests.
