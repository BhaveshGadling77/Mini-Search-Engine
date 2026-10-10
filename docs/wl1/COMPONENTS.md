# Component Documentation — Worklet 1: Crawler & Document Model

**Package:** `crawler/` · **Language:** Python 3.12

This document explains every component built for Worklet 1, its purpose, its
public API, and the design decisions behind it. It is the source of truth for
maintainers alongside the code and the top-level `README.md`.

---

## High-Level Flow

```
seeds.txt ──► main.py ──► CrawlEngine
                            │
                            ├─► URLFrontier (BFS queue + visited set)
                            │        │  pop(url)
                            ▼        ▼
                        Fetcher (HTTP GET, per-domain politeness, robots.txt)
                            │  raw HTML
                            ▼
                        parser.parse_page(html, url)
                            │         │
                            ▼         ▼
                        clean text   outbound URLs ──────────────┐
                            │                                    │
                            ▼                                    │
                        tokenizer (split → lower → drop stopwords) │
                            │                                    │
                            ▼                                    │
                        Document (model) ──► JSONLStore           │
                                              │                  │
                                              ▼                  │
                                        data/corpus.jsonl        │
                                                                 │
                          (outbound URLs fed back to frontier) ◄─┘
```

---

## File Tree

```
Mini-Search-Engine/
├── main.py                  # CLI entry point
├── seeds.txt                # seed URLs (one per line)
├── requirements.txt         # requests, lxml, pytest
├── .gitignore               # ignores data/, logs/, __pycache__/
├── crawler/
│   ├── __init__.py          # public re-exports
│   ├── config.py            # all tunables + stop-word list
│   ├── models.py            # Document dataclass
│   ├── frontier.py          # URLFrontier (BFS)
│   ├── fetcher.py           # Fetcher (HTTP)
│   ├── parser.py            # parse_page / parse_html / extract_links
│   ├── tokenizer.py         # tokenize()
│   ├── store.py             # JSONLStore
│   └── engine.py            # CrawlEngine (orchestration)
├── docs/
│   └── COMPONENTS.md        # this file
├── data/                    # generated (gitignored)
│   └── corpus.jsonl
└── tests/
    ├── __init__.py
    ├── test_frontier.py
    ├── test_fetcher.py
    ├── test_parser.py
    ├── test_tokenizer.py
    └── test_store.py
```

---

## 1. `crawler/config.py`

**Purpose:** Single source of all runtime tunables and the built-in stop-word
list. Keeps business logic clean; the crawl can be re-shaped without touching
any other module.

| Symbol               | Default                                       | Meaning                                         |
| -------------------- | --------------------------------------------- | ----------------------------------------------- |
| `USER_AGENT`         | `MiniSearchEngine/1.0 (+educational-crawler)` | HTTP header                                     |
| `REQUEST_TIMEOUT_S`  | `10.0`                                        | Per-request timeout                             |
| `POLITENESS_DELAY_S` | `1.0`                                         | Minimum gap between requests to the same domain |
| `MAX_RETRIES`        | `3`                                           | Retries on transient failure                    |
| `RETRY_BACKOFF_S`    | `2.0`                                         | Exponential backoff base                        |
| `RESPECT_ROBOTS_TXT` | `True`                                        | Honor robots.txt                                |
| `MAX_PAGES`          | `100`                                         | Default document budget                         |
| `SEED_FILE`          | `<project_root>/seeds.txt`                    | Default seed file (absolute path)               |
| `CORPUS_PATH`        | `<project_root>/data/corpus.jsonl`            | Default output (absolute path)                  |
| `LOG_PATH`           | `<project_root>/logs/crawler.log`             | Default log (absolute path)                     |
| `STOPWORDS`          | frozen ~175 words                             | No `nltk` dependency                            |

**Decision:** Stop-words are a self-contained `frozenset` of common English
function words / pronouns / contractions, normalized to alphanumeric fragments
so they match the tokenizer output exactly.

**Decision:** All file paths are resolved as absolute paths from `__file__`
using `pathlib.Path`, so the project works correctly regardless of the caller's
working directory.

---

## 2. `crawler/models.py` — `Document`

**Purpose:** The immutable unit of persistence and the join-key carrier for
Worklet 2 (indexing) and Worklet 3 (ranking).

```python
@dataclasses.dataclass(frozen=True)
class Document:
    doc_id: str              # "d-3f2a1b9c"
    url: str
    text: str                # clean visible text
    tokens: tuple[str, ...]  # normalized token tuple (immutable)
    meta: dict[str, Any]     # crawled_at, content_length, status, depth
```

**Methods:**

- `to_dict()` — JSON-serializable record; the frozen schema contract.
  Converts `tokens` tuple → list for JSON compatibility.
- `new_doc_id()` — `"d-" + uuid4().hex[:8]`.
- `now_iso()` — current UTC ISO 8601 timestamp.

**Decision:** `doc_id` is a truncated UUID, not a sequential counter. This is
collision-safe across restarts/parallel runs and removes the earlier
`doc_00017` placeholder format from the spec.

**Decision:** `tokens` is stored as `tuple[str, ...]` (not `list`) to uphold
the `frozen=True` immutability contract — prevents accidental mutation after
construction.

---

## 3. `crawler/frontier.py` — `URLFrontier`

**Purpose:** Enforce BFS ordering and prevent re-fetch loops using a FIFO
`collections.deque` + a `set` of canonicalized URLs.

**Public API:**

- `add(url) -> str | None` — normalize and enqueue if new; returns canonical
  URL or `None` if invalid/visited/filtered.
- `pop() -> str | None` — next URL in FIFO order.
- `empty()`, `__len__()`, `visited` property.
- `normalize(url) -> str | None` — static, 5-step canonicalization.

**Normalization pipeline:**

1. Scheme restricted to `http`/`https` (lowercased).
2. Fragment (`#...`) stripped.
3. Scheme + netloc lowercased.
4. Default ports (`:80`, `:443`) removed.
5. Empty path → `/`; trailing slashes collapsed.

**Decision:** Optional `allowed_domains` filter keeps the crawl within target
sites for the MVP. `add()` returning the canonical URL lets the engine map the
BFS depth onto the normalized key.

---

## 4. `crawler/fetcher.py` — `Fetcher`

**Purpose:** Retrieve raw HTML over HTTP/HTTPS with politeness and resilience.
Never raises to the caller — malformed URLs, timeouts and HTTP errors are
logged and yield `None`.

**Public API:**

- `fetch(url) -> str | None` — fetch with politeness + robots.txt + retries.
- `close()` — release the `requests.Session` and its connection pool.

**Behavior:**

- `requests.Session` for connection reuse.
- **Per-domain** politeness delay: tracks `_last_request_time` as a
  `dict[str, float]` keyed by domain, so requests to different domains
  don't wait on each other.
- `robots.txt` compliance via `urllib.robotparser` (cached per origin;
  missing robots.txt → allow by default).
- Retries transient failures (429/5xx) with exponential backoff.
- `None` on final failure — the engine skips the page and continues.

**Note on parameter defaults:** Constructor uses `is not None` checks (not
`or`) so that passing `0` for `politeness_delay_s` or `timeout` works
correctly instead of falling back to config defaults.

---

## 5. `crawler/parser.py` — `parse_page` / `parse_html` / `extract_links`

**Purpose:** Turn raw HTML into clean visible text and outbound link lists
using `lxml.html` (no `beautifulsoup4`).

- `parse_page(html, base_url) -> (str, list[str])` — **single-pass**: parses
  the DOM once, extracts both clean text and absolute links. Used by the
  engine in the crawl loop to avoid double parsing.
- `parse_html(html) -> str` — removes `script/style/noscript/head/template`,
  extracts text content, collapses whitespace. Malformed HTML degrades to `""`.
- `extract_links(html, base_url) -> list[str]` — collects absolute URLs from
  every `<a href>` using `urllib.parse.urljoin`. Malformed HTML yields `[]`.

**Internal helper:** `_parse_dom(html) -> lxml element | None` — shared DOM
parser that returns `None` on failure.

**Decision:** Both standalone functions and `parse_page()` degrade gracefully
rather than raise, satisfying the robustness constraint.

---

## 6. `crawler/tokenizer.py` — `tokenize`

**Purpose:** Token normalization pipeline, budgeted ≤ 2 s/page.

1. `re.findall(r"[a-zA-Z0-9]+", text)` — word-boundary split that drops stray
   punctuation in a single pass.
2. `str.lower()`.
3. Drop stop-words via `config.STOPWORDS`.

Returns `list[str]`; empty/`None` input → `[]`.

**Decision:** A single regex pass replaces the older separate strip-punctuation
step, eliminating edge cases around stray punctuation.

---

## 7. `crawler/store.py` — `JSONLStore`

**Purpose:** Append-only JSONL persistence, one document per line.

- `append(document)` — writes one JSON line and flushes.
- `close()`, plus context-manager support (`__enter__`/`__exit__`).

**Decision:** Append-only + `flush()` after every record means a partial crawl
(interrupted mid-run) still produces a usable corpus. Supports the "MVP
handoff" of a partial corpus to Worklet 2.

---

## 8. `crawler/engine.py` — `CrawlEngine`

**Purpose:** Orchestrates the BFS feedback loop: pop → fetch → parse_page →
tokenize → persist → enqueue.

- Constructor accepts `seeds`, `max_pages`, `allowed_domains`, and optional
  injected `fetcher`/`store` (enables testing with mocks).
- `run() -> int` — returns the number of documents persisted.
- Uses `parse_page()` for single-pass HTML parsing (text + links in one call).
- Tracks BFS `depth` per URL and records it in `meta`.
- `close()` releases **both** the store file handle and the fetcher's HTTP
  session.

**Note on parameter defaults:** `max_pages` uses `is not None` (not `or`) so
that passing `0` works correctly.

---

## 9. `main.py`

**Purpose:** CLI entry point.

- Flags: `--seeds`, `--max-pages`, `--allowed-domains`, `--corpus`, `--log`.
- Loads seed URLs (ignores blank lines and `#` comments).
- Configures logging to both file and console.
- Runs the engine and reports the count persisted.

Usage:

```bash
pip install -r requirements.txt
python main.py --seeds seeds.txt --max-pages 100
```

---

## Design Decisions Summary

| Decision                            | Rationale                                                           |
| ----------------------------------- | ------------------------------------------------------------------- |
| `lxml` (not `beautifulsoup4`)       | Already installed; fast, robust HTML parsing.                       |
| Built-in stopwords (not `nltk`)     | Avoids ~70 MB dependency; deterministic.                            |
| JSONL corpus                        | Streamable, `grep`-friendly, append-safe.                           |
| UUID `doc_id`                       | Collision-safe; no global counter; removes `doc_00017` placeholder. |
| Never raise on network/parse errors | Satisfies robustness constraint; log-and-skip.                      |
| Robots.txt + per-domain politeness  | Polite crawling per SRS constraints; doesn't penalize cross-domain. |
| `parse_page()` single-pass          | Avoids parsing the same HTML twice in the hot loop.                 |
| `tuple` tokens on frozen dataclass  | True immutability — `list` on `frozen=True` is a leaky abstraction. |
| `is not None` defaults (not `or`)   | `0` is a valid value for delay/timeout/max_pages.                   |
| Absolute paths via `pathlib`        | Works regardless of the caller's working directory.                 |

## Testing

```
tests/
├── __init__.py          # package marker for consistent discovery
├── test_frontier.py     # normalization, dedup, domain filter
├── test_fetcher.py      # mocked: 200 success, 404, connection error, 503 retry, delay=0
├── test_parser.py       # stripping, relative link resolution, malformed input, parse_page
├── test_tokenizer.py    # lowercasing, punctuation, stopwords
└── test_store.py        # JSONL append + schema shape + tuple→list serialization
```

Run: `pytest`
