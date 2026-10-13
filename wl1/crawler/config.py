"""Central configuration for the crawler.

All tunables live here so the crawl can be re-shaped without touching
business logic: politeness, request limits, file paths, and the built-in
stop-word list (avoids an external `nltk` dependency).

Values may be overridden at runtime via `main.py` CLI flags.
"""

from __future__ import annotations

from pathlib import Path

# ─── Resolved project root (works regardless of working directory) ────────
def _resolve_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "data").is_dir() and ((parent / ".git").exists() or (parent / "README.md").exists()):
            return parent
    return Path(__file__).resolve().parents[2]


_ROOT = _resolve_project_root()

# --- HTTP / politeness -----------------------------------------------------
USER_AGENT = "MiniSearchEngine/1.0 (+educational-crawler)"
REQUEST_TIMEOUT_S = 10.0
POLITENESS_DELAY_S = 1.0
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0
RESPECT_ROBOTS_TXT = True

# --- Crawl limits ---------------------------------------------------------
MAX_PAGES = 500
MAX_DEPTH = 5
MAX_LINKS_PER_PAGE = 3

# --- File paths (absolute, resolved from project root) --------------------
_seeds_candidate = _ROOT / "seeds.txt"
if not _seeds_candidate.is_file():
    _wl1_seeds = _ROOT / "wl1" / "seeds.txt"
    if _wl1_seeds.is_file():
        _seeds_candidate = _wl1_seeds

SEED_FILE = str(_seeds_candidate)
DATA_DIR = str(_ROOT / "data")
CORPUS_PATH = str(_ROOT / "data" / "corpus.jsonl")
LOG_DIR = str(_ROOT / "logs")
LOG_PATH = str(_ROOT / "logs" / "crawler.log")

# --- Stop-words -----------------------------------------------------------
# A self-contained ~175-word English stop-word list (common function words,
# pronouns, auxiliaries and contractions). Normalized to lower-case and
# already split into alphanumeric fragments to match the tokenizer output.
STOPWORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "ain", "all",
        "am", "an", "and", "any", "are", "aren", "as", "at", "be", "because",
        "been", "before", "being", "below", "between", "both", "but", "by",
        "can", "couldn", "d", "did", "didn", "do", "does", "doesn", "doing",
        "don", "down", "during", "each", "few", "for", "from", "further",
        "had", "hadn", "has", "hasn", "have", "haven", "having", "he", "her",
        "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
        "in", "into", "is", "isn", "it", "its", "itself", "just", "ll", "m",
        "ma", "me", "mightn", "more", "most", "mustn", "my", "myself",
        "needn", "no", "nor", "not", "now", "o", "of", "off", "on", "once",
        "only", "or", "other", "our", "ours", "ourselves", "out", "over",
        "own", "re", "same", "shan", "she", "should", "shouldn", "so", "some",
        "such", "t", "than", "that", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "this", "those",
        "through", "to", "too", "under", "until", "up", "ve", "very", "was",
        "wasn", "we", "were", "weren", "what", "when", "where", "which",
        "while", "who", "whom", "why", "will", "with", "won", "wouldn", "y",
        "you", "your", "yours", "yourself", "yourselves",
    }
)