from wallet_twin.retrieval import BM25Index, EvidenceDocument, hybrid_retrieve


def docs():
    return [
        EvidenceDocument("OBS-1", "BHP cross border USD activity", "observed", "2026-06-30", {}),
        EvidenceDocument("ASM-1", "generic trade finance share prior", "assumption", "2026-06-30", {}),
        EvidenceDocument("MOD-1", "modelled liquidity wallet", "model", "2026-06-30", {}),
    ]


def test_bm25_returns_relevant_evidence():
    result = BM25Index(docs()).search("USD cross border", limit=1)
    assert result[0][0].evidence_id == "OBS-1"


def test_hybrid_rerank_preserves_quality():
    result = hybrid_retrieve(docs(), "trade activity share", limit=2)
    assert len(result) == 2
    assert result[0].evidence_id in {"OBS-1", "ASM-1"}

