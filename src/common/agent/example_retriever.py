import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Any, Protocol

from common.annotation.component import Component

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
logger = logging.getLogger(__name__)


class ExampleRetriever(Protocol):
    """Search interface that can later be implemented with semantic retrieval."""

    def search(
        self, query: str, examples_path: Path, top_k: int = 5
    ) -> list[dict[str, Any]]: ...


@Component
class BM25ExampleRetriever:
    """Small in-process BM25 retriever for JSON prompt examples."""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._indexes: dict[Path, dict[str, Any]] = {}

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [token.lower() for token in _TOKEN_PATTERN.findall(value)]

    def _document_tokens(self, example: dict[str, Any]) -> list[str]:
        return self._tokenize(
            f"{example.get('input', '')} "
            f"{json.dumps(example.get('output', {}), ensure_ascii=False)} "
            f"{' '.join(example.get('steps', []))}"
        )

    def _get_index(self, examples_path: Path) -> dict[str, Any]:
        examples_path = examples_path.resolve()
        if examples_path not in self._indexes:
            examples: list[dict[str, Any]] = json.loads(
                examples_path.read_text(encoding="utf-8")
            )
            documents = [self._document_tokens(example) for example in examples]
            document_lengths = [len(document) for document in documents]
            document_frequency: dict[str, int] = {}
            for document in documents:
                for token in set(document):
                    document_frequency[token] = document_frequency.get(token, 0) + 1
            self._indexes[examples_path] = {
                "examples": examples,
                "documents": documents,
                "document_lengths": document_lengths,
                "average_document_length": (
                    sum(document_lengths) / len(document_lengths)
                    if document_lengths
                    else 0.0
                ),
                "document_frequency": document_frequency,
            }
        return self._indexes[examples_path]

    def search(
        self, query: str, examples_path: Path, top_k: int = 5
    ) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        index = self._get_index(examples_path)
        examples = index["examples"]
        documents = index["documents"]
        average_document_length = index["average_document_length"]
        document_frequency = index["document_frequency"]
        if not examples or top_k <= 0:
            logger.info(
                "Example retrieval completed: backend=BM25 query_chars=%d "
                "requested_top_k=%d result_count=0 retrieval_time_ms=%.2f",
                len(query),
                top_k,
                (time.perf_counter() - started_at) * 1000,
            )
            return []

        query_tokens = self._tokenize(query)
        query_terms = set(query_tokens)
        document_count = len(documents)
        scored_examples: list[tuple[float, int, dict[str, Any]]] = []
        for document_index, document in enumerate(documents):
            frequencies = {token: document.count(token) for token in query_terms}
            score = 0.0
            for token, frequency in frequencies.items():
                if not frequency:
                    continue
                token_document_frequency = document_frequency.get(token, 0)
                idf = math.log(
                    1
                    + (document_count - token_document_frequency + 0.5)
                    / (token_document_frequency + 0.5)
                )
                length_norm = (
                    1 - self.b + self.b * len(document) / average_document_length
                    if average_document_length
                    else 1
                )
                score += (
                    idf
                    * (frequency * (self.k1 + 1))
                    / (frequency + self.k1 * length_norm)
                )
            if score > 0:
                scored_examples.append(
                    (score, document_index, examples[document_index])
                )

        scored_examples.sort(key=lambda item: (-item[0], item[1]))
        results = [example for _, _, example in scored_examples[:top_k]]
        logger.info(
            "Example retrieval completed: backend=BM25 query_chars=%d "
            "requested_top_k=%d result_count=%d retrieval_time_ms=%.2f",
            len(query),
            top_k,
            len(results),
            (time.perf_counter() - started_at) * 1000,
        )
        return results


def render_examples_xml(examples: list[dict[str, Any]]) -> str:
    """Render retrieved examples in the XML format expected by the agents."""
    rendered = "\n".join(
        f"<example>\n{json.dumps(example, ensure_ascii=False, indent=2)}\n</example>"
        for example in examples
    )
    return (
        "<examples>\n"
        "Each example has an input request and the expected output. Optional "
        "steps are concise action summaries: use them as a checklist, do not "
        "return them as output or add unrequested work.\n"
        f"{rendered}\n</examples>"
    )


def build_example_context(
    retriever: ExampleRetriever, query: str, examples_path: Path, top_k: int = 5
) -> str:
    """Return top matching examples for appending to an agent request."""
    examples = retriever.search(query, examples_path, top_k=top_k)
    return render_examples_xml(examples) if examples else ""
