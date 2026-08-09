from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class EvidenceDocument:
    evidence_id: str
    text: str
    source_type: str
    available_date: str
    payload: dict


class BM25Index:
    """Tiny dependency-free lexical retriever for offline evidence packs."""

    def __init__(self, documents: Iterable[EvidenceDocument], k1: float = 1.5, b: float = 0.75):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(doc.text) for doc in self.documents]
        self.tf = [Counter(tokens) for tokens in self.tokens]
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.avg_length = sum(self.lengths) / len(self.lengths) if self.lengths else 1.0
        self.df = Counter()
        for tokens in self.tokens:
            self.df.update(set(tokens))

    def search(self, query: str, limit: int = 8) -> list[tuple[EvidenceDocument, float]]:
        q = tokenize(query)
        n = max(1, len(self.documents))
        scored: list[tuple[EvidenceDocument, float]] = []
        for idx, doc in enumerate(self.documents):
            score = 0.0
            length_norm = 1.0 - self.b + self.b * self.lengths[idx] / self.avg_length
            for token in q:
                freq = self.tf[idx].get(token, 0)
                if not freq:
                    continue
                idf = math.log(1.0 + (n - self.df[token] + 0.5) / (self.df[token] + 0.5))
                score += idf * freq * (self.k1 + 1.0) / (freq + self.k1 * length_norm)
            if score > 0:
                scored.append((doc, score))
        return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]


def hybrid_retrieve(documents: Iterable[EvidenceDocument], query: str, limit: int = 8) -> list[EvidenceDocument]:
    """Current offline implementation: BM25 plus deterministic evidence-quality rerank.

    The interface intentionally leaves a clean seam for embeddings. Lexical score,
    recency, and source quality remain visible rather than hidden in an agent loop.
    """

    quality = {"observed": 1.0, "public": 0.95, "derived": 0.80, "model": 0.50, "assumption": 0.30}
    results = BM25Index(documents).search(query, limit=max(limit * 2, 10))
    reranked = sorted(results, key=lambda item: item[1] * quality.get(item[0].source_type, 0.40), reverse=True)
    return [doc for doc, _ in reranked[:limit]]

