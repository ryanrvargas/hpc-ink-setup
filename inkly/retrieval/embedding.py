from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List

TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]+")


class TfidfEmbedder:
    """
    Small, dependency-free TF-IDF embedder.

    This is deliberately simple for Milestone 2.5 Issue #83:
    - deterministic
    - easy to test
    - easy to run on HPC without heavyweight ML dependencies

    The interface is intentionally model-like so a transformer encoder can
    replace it later without forcing runtime or retriever redesign.
    """

    def __init__(self) -> None:
        self._idf: Dict[str, float] = {}
        self._fitted = False

    @staticmethod
    def tokenize(text: str) -> List[str]:
        if not text:
            return []
        return [tok.lower() for tok in TOKEN_RE.findall(text)]

    def fit(self, texts: Iterable[str]) -> None:
        texts = list(texts)
        num_docs = len(texts)
        if num_docs == 0:
            self._idf = {}
            self._fitted = True
            return

        doc_freq: Counter[str] = Counter()
        for text in texts:
            unique = set(self.tokenize(text))
            doc_freq.update(unique)

        self._idf = {
            token: math.log((1.0 + num_docs) / (1.0 + freq)) + 1.0
            for token, freq in doc_freq.items()
        }
        self._fitted = True

    def encode(self, text: str) -> Dict[str, float]:
        if not self._fitted:
            raise RuntimeError("TfidfEmbedder must be fitted before encode()")

        tokens = self.tokenize(text)
        if not tokens:
            return {}

        counts = Counter(tokens)
        total = float(sum(counts.values()))
        vec: Dict[str, float] = {}

        for token, count in counts.items():
            if token not in self._idf:
                continue
            tf = count / total
            vec[token] = tf * self._idf[token]

        return self._normalize(vec)

    @staticmethod
    def _normalize(vec: Dict[str, float]) -> Dict[str, float]:
        if not vec:
            return {}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm == 0.0:
            return dict(vec)
        return {k: v / norm for k, v in vec.items()}


def cosine_similarity(left: Dict[str, float], right: Dict[str, float]) -> float:
    if not left or not right:
        return 0.0

    if len(left) > len(right):
        left, right = right, left

    return sum(value * right.get(token, 0.0) for token, value in left.items())
