from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List

# Regex used to break text into tokens.
# This keeps letters, numbers, underscores, and hyphens together.
#
# Examples:
# - "queue-status" stays as one token
# - "GPU_4" stays as one token
TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]+")


class TfidfEmbedder:
    """
    Small, dependency-free TF-IDF embedder.

    This class converts text into a sparse numeric vector so text can be
    compared mathematically.

    High-level idea:
    - tokenize text into words
    - compute IDF values from a corpus during fit()
    - compute TF-IDF weights during encode()
    - normalize the final vector so cosine similarity works cleanly

    Why TF-IDF is used here:
    - deterministic
    - lightweight
    - easy to test
    - works without external ML libraries

    This is intentionally simple, but the interface is structured so it can
    later be replaced with a more advanced embedding model if needed.
    """

    def __init__(self) -> None:
        # Stores inverse document frequency values for each known token.
        # Example:
        # {
        #   "queue": 1.4,
        #   "gaussian": 2.1,
        # }
        self._idf: Dict[str, float] = {}

        # Tracks whether fit() has been called.
        # encode() should not run before the embedder has learned IDF values.
        self._fitted = False

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Split text into lowercase tokens.

        This is the first step in the embedding process.
        The result is a simple list of normalized tokens.

        Example:
        "How busy is the GPU queue?"
        -> ["how", "busy", "is", "the", "gpu", "queue"]
        """
        if not text:
            return []
        return [tok.lower() for tok in TOKEN_RE.findall(text)]

    def fit(self, texts: Iterable[str]) -> None:
        """
        Fit the embedder on a corpus of texts.

        This computes IDF (inverse document frequency) values.
        IDF gives more weight to tokens that appear in fewer documents
        and less weight to very common tokens.

        Example intuition:
        - a token like "the" would get low value if it appears everywhere
        - a token like "gaussian" would get higher value if it appears rarely

        Args:
            texts: Collection of text documents used as the fitting corpus
        """
        texts = list(texts)
        num_docs = len(texts)

        # Empty corpus means there is nothing to learn.
        # Mark as fitted anyway so encode() can safely return empty vectors later.
        if num_docs == 0:
            self._idf = {}
            self._fitted = True
            return

        # Document frequency counts how many documents contain each token at least once.
        # This is different from raw token count.
        doc_freq: Counter[str] = Counter()
        for text in texts:
            unique = set(self.tokenize(text))
            doc_freq.update(unique)

        # Compute smoothed IDF values.
        #
        # Formula:
        # log((1 + num_docs) / (1 + freq)) + 1
        #
        # Smoothing avoids division by zero and keeps values stable.
        self._idf = {
            token: math.log((1.0 + num_docs) / (1.0 + freq)) + 1.0
            for token, freq in doc_freq.items()
        }

        self._fitted = True

    def encode(self, text: str) -> Dict[str, float]:
        """
        Encode one text string into a normalized TF-IDF vector.

        Steps:
        - tokenize the input text
        - count how often each token appears
        - compute term frequency (TF)
        - multiply TF by learned IDF
        - normalize the vector

        Returns:
            Sparse dictionary mapping token -> weight

        Raises:
            RuntimeError: If fit() has not been called yet
        """
        if not self._fitted:
            raise RuntimeError("TfidfEmbedder must be fitted before encode()")

        tokens = self.tokenize(text)
        if not tokens:
            return {}

        # Raw token counts for this single text.
        counts = Counter(tokens)

        # Total token count used to convert raw counts into term frequency.
        total = float(sum(counts.values()))

        vec: Dict[str, float] = {}

        for token, count in counts.items():
            # Ignore tokens that were never seen during fit().
            # If a token is not in the fitted vocabulary, it gets no weight.
            if token not in self._idf:
                continue

            # TF = local importance inside this text.
            tf = count / total

            # TF-IDF = local importance * global rarity
            vec[token] = tf * self._idf[token]

        # Normalize so vector length is consistent across texts.
        return self._normalize(vec)

    @staticmethod
    def _normalize(vec: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize a vector to unit length.

        This is important because cosine similarity works best when vectors
        are length-normalized. It makes comparison focus more on direction
        than raw magnitude.

        If the vector is empty, return an empty dictionary.
        If the norm is zero, return the vector unchanged.
        """
        if not vec:
            return {}

        # Euclidean norm of the vector.
        norm = math.sqrt(sum(v * v for v in vec.values()))

        if norm == 0.0:
            return dict(vec)

        return {k: v / norm for k, v in vec.items()}


def cosine_similarity(left: Dict[str, float], right: Dict[str, float]) -> float:
    """
    Compute cosine similarity between two sparse vectors.

    Cosine similarity measures how aligned two vectors are.
    Higher value means the texts are more similar in meaning
    under this TF-IDF representation.

    Notes:
    - returns 0.0 if either vector is empty
    - swaps vectors if needed so iteration happens over the smaller one
      for efficiency
    """
    if not left or not right:
        return 0.0

    # Iterate over the smaller vector to reduce lookup work.
    if len(left) > len(right):
        left, right = right, left

    # Sparse dot product.
    return sum(value * right.get(token, 0.0) for token, value in left.items())
