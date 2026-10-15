"""
Synthetic corpus + labelled queries for end-to-end evaluation.

The hand-written ``LABELLED_QUERIES`` in ``dataset.py`` refer to doc ids of a
corpus that does not exist yet (they are placeholders for the real W1/W2
corpus).  To exercise the *whole* pipeline (QueryEngine, cache, concurrency)
before that corpus exists, this module generates a deterministic corpus of 240
documents and 40 labelled queries whose relevance is known by construction
(a query is relevant to the documents written about its sub-topic).

Queries use the same dict format as ``dataset.py``::

    {"query": "...", "relevant_docs": [ids...]}

For the final report, replace this with hand labels on the real corpus
(``load_queries(path)`` reads such a JSON file).
"""

from __future__ import annotations

import json
import random

# topic -> (core terms, {sub-topic: terms})
_TOPICS: dict[str, tuple[list[str], dict[str, list[str]]]] = {
    "machine learning": (
        ["learning", "model", "training", "data", "prediction", "algorithm"],
        {
            "neural networks": ["neuron", "backpropagation", "perceptron", "activation", "layers"],
            "decision trees": ["split", "entropy", "pruning", "forest", "gini"],
            "clustering": ["centroid", "kmeans", "cluster", "dendrogram", "silhouette"],
            "reinforcement learning": ["reward", "policy", "agent", "episode", "qlearning"],
        },
    ),
    "databases": (
        ["database", "table", "query", "record", "storage", "schema"],
        {
            "indexing": ["btree", "hashindex", "bitmap", "clustered", "lookup"],
            "transactions": ["commit", "rollback", "isolation", "atomicity", "deadlock"],
            "normalization": ["functional", "dependency", "decomposition", "redundancy", "bcnf"],
            "nosql": ["document", "keyvalue", "sharding", "replica", "eventual"],
        },
    ),
    "operating systems": (
        ["kernel", "process", "memory", "system", "resource", "hardware"],
        {
            "scheduling": ["quantum", "roundrobin", "priority", "preemption", "dispatcher"],
            "virtual memory": ["paging", "pagefault", "tlb", "swap", "segmentation"],
            "file systems": ["inode", "directory", "journaling", "block", "mount"],
            "concurrency": ["mutex", "semaphore", "thread", "race", "monitor"],
        },
    ),
    "computer networks": (
        ["network", "packet", "protocol", "layer", "router", "bandwidth"],
        {
            "tcp": ["handshake", "congestion", "retransmission", "window", "segment"],
            "routing": ["dijkstra", "bgp", "ospf", "gateway", "forwarding"],
            "http": ["request", "response", "cookie", "header", "caching"],
            "wireless": ["antenna", "spectrum", "modulation", "handoff", "interference"],
        },
    ),
    "cryptography": (
        ["encryption", "key", "cipher", "secure", "message", "secret"],
        {
            "public key": ["rsa", "prime", "modulus", "diffie", "certificate"],
            "hashing": ["digest", "collision", "sha", "preimage", "checksum"],
            "block ciphers": ["aes", "rounds", "feistel", "sbox", "mode"],
            "signatures": ["signing", "verification", "nonrepudiation", "dsa", "authentic"],
        },
    ),
    "compilers": (
        ["compiler", "source", "code", "program", "translation", "syntax"],
        {
            "parsing": ["grammar", "lexer", "token", "lr", "ambiguity"],
            "optimization": ["inlining", "loopunrolling", "deadcode", "peephole", "constant"],
            "code generation": ["register", "instruction", "assembly", "target", "allocation"],
            "type systems": ["inference", "polymorphism", "typecheck", "generics", "subtyping"],
        },
    ),
    "web development": (
        ["web", "browser", "page", "server", "client", "application"],
        {
            "frontend": ["javascript", "dom", "css", "react", "component"],
            "backend": ["endpoint", "middleware", "session", "rest", "framework"],
            "security": ["xss", "csrf", "injection", "sanitize", "cors"],
            "performance": ["lazyload", "bundle", "minify", "cdn", "latency"],
        },
    ),
    "algorithms": (
        ["algorithm", "complexity", "input", "efficient", "problem", "analysis"],
        {
            "sorting": ["quicksort", "mergesort", "heapsort", "pivot", "stable"],
            "graphs": ["vertex", "edge", "traversal", "spanning", "shortest"],
            "dynamic programming": ["memoization", "subproblem", "knapsack", "recurrence", "tabulation"],
            "hashing tables": ["bucket", "probing", "chaining", "loadfactor", "rehash"],
        },
    ),
    "software engineering": (
        ["software", "project", "team", "requirement", "design", "quality"],
        {
            "testing": ["unittest", "coverage", "mock", "regression", "integration"],
            "agile": ["sprint", "scrum", "backlog", "standup", "retrospective"],
            "version control": ["commit", "branch", "merge", "rebase", "repository"],
            "architecture": ["microservice", "monolith", "layered", "coupling", "cohesion"],
        },
    ),
    "computer graphics": (
        ["graphics", "image", "render", "scene", "pixel", "surface"],
        {
            "ray tracing": ["ray", "reflection", "refraction", "shadow", "intersection"],
            "shaders": ["vertex", "fragment", "glsl", "pipeline", "texture"],
            "animation": ["keyframe", "skeleton", "interpolation", "rigging", "motion"],
            "geometry": ["mesh", "polygon", "tessellation", "normal", "bezier"],
        },
    ),
}

_FILLER = (
    "important common approach typically used often considered several different "
    "method result property example general useful practical modern basic standard "
    "efficient overview concept technique study widely understood"
).split()

_TEMPLATES = [
    "{a} and {b} are central to {c}.",
    "A typical discussion of {a} covers {b} together with {c}.",
    "In practice {a} depends on {b} while {c} is {f}.",
    "Researchers study {a}, {b} and {c} in a {f} way.",
    "The {a} of a system relates closely to {b} and {c}.",
]

DOCS_PER_SUBTOPIC = 6


def build_synthetic_corpus(seed: int = 7) -> tuple[list[dict], list[dict]]:
    """Return ``(documents, labelled_queries)`` — 240 docs, 40 queries."""
    rng = random.Random(seed)
    topic_names = list(_TOPICS)
    documents: list[dict] = []
    queries: list[dict] = []
    doc_id = 0

    for topic, (core, subs) in _TOPICS.items():
        for sub, sub_terms in subs.items():
            relevant: set[int] = set()
            for n in range(DOCS_PER_SUBTOPIC):
                other_topic = rng.choice([t for t in topic_names if t != topic])
                noise_pool = [w for ws in _TOPICS[other_topic][1].values() for w in ws]
                sentences = []
                for _ in range(rng.randint(4, 12)):
                    pool = sub_terms if rng.random() < 0.55 else core
                    a, b = rng.sample(pool, 2)
                    c = rng.choice(noise_pool if rng.random() < 0.15 else pool)
                    sentences.append(rng.choice(_TEMPLATES).format(a=a, b=b, c=c, f=rng.choice(_FILLER)))
                documents.append(
                    {
                        "id": doc_id,
                        "title": f"{topic.title()}: {sub.title()} (note {n + 1})",
                        "url": f"https://example.edu/{topic.replace(' ', '-')}/{sub.replace(' ', '-')}/{n + 1}",
                        "text": " ".join(sentences),
                    }
                )
                relevant.add(doc_id)
                doc_id += 1
            query_terms = rng.sample(sub_terms, 2) + [rng.choice(core)]
            queries.append({"query": " ".join(query_terms), "relevant_docs": sorted(relevant),
                            "description": f"{topic} / {sub}"})

    return documents, queries


def load_queries(path: str) -> list[dict]:
    """Load hand-labelled queries from JSON: ``[{"query", "relevant_docs"}, ...]``."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw["queries"] if isinstance(raw, dict) else raw
