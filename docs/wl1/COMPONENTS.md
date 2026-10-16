# Component Documentation — Worklet 1: Crawler & Document Model

**Package:** `wl1/crawler/` · **Language:** Python 3.12+

This document explains every component built for Worklet 1, its purpose, its
public API, and the design decisions behind it. It is the source of truth for
maintainers alongside the code, `README.md`, and the Worklet 1 UML diagram
(`wl1/Worklet1UML.drawio`).

---

## High-Level Flow

```
wl1/seeds.txt ──► wl1/main.py ──► CrawlEngine
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
                    clean text with breaks   outbound URLs ──────────────┐
                                    │                                    │
                                    ▼                                    │
                        tokenizer.tokenize_segments()                    │
                         (split on sentinel → alphanum → stopwords)      │
                                    │                                    │
                                    ├─► token_segments (nested tuples)   │
                                    ├─► flat tokens                      │
                                    ▼                                    │
                                Document (model) ──► JSONLStore           │
                                                      │                  │
                                                      ▼                  │
                                                 data/crawler.json        │
                                                                         │
                                  (outbound URLs fed back to frontier) ◄─┘
```

---

## File Tree

```
Mini-Search-Engine/
├── .gitignore               # ignores logs/, __pycache__/, etc.
├── CONTRIBUTING.md
├── README.md                # project-wide architecture & worklet breakdown
├── data/
│   └── crawler.json         # 500 crawled documents (JSONL format, schema-frozen)
├── docs/
│   └── wl1/
│       └── COMPONENTS.md    # this documentation file
├── tests/
│   └── wl1/
│       ├── __init__.py      # test package marker
│       ├── conftest.py      # configures sys.path to discover wl1/
│       ├── test_fetcher.py  # mocked HTTP, politeness delay, retry logic, robots.txt
│       ├── test_frontier.py # URL normalization, deduplication, domain filtering
│       ├── test_parser.py   # text extraction, link resolution, section breaks
│       ├── test_store.py    # JSONL persistence, Document schema serialization
│       └── test_tokenizer.py# tokenization, stop-words, per-section segments
└── wl1/
    ├── Worklet1UML.drawio   # UML architecture & class diagram
    ├── main.py              # CLI entry point
    ├── requirements.txt     # requests, lxml, pytest dependencies
    ├── seeds.txt            # curated seed URLs (one per line)
    └── crawler/
        ├── __init__.py      # public package re-exports
        ├── config.py        # central tunables, crawler limits, stop-words
        ├── engine.py        # CrawlEngine (BFS orchestration & loop)
        ├── fetcher.py       # Fetcher (HTTP GET, politeness, robots.txt)
        ├── frontier.py      # URLFrontier (BFS deque, normalization, dedup)
        ├── models.py        # Document dataclass (schema contract for W2/W3)
        ├── parser.py        # parse_page, parse_html, extract_links, SECTION_BREAK
        ├── store.py         # JSONLStore (append-only file writer)
        └── tokenizer.py     # tokenize(), tokenize_segments()
```

---

## 1. `wl1/crawler/config.py`

**Purpose:** Single source of all runtime tunables, crawl limits, absolute paths,
and the built-in stop-word list. Keeps business logic decoupled from configuration;
the crawl can be re-shaped without touching any other module.

| Symbol               | Default                                       | Meaning                                             |
| -------------------- | --------------------------------------------- | --------------------------------------------------- |
| `USER_AGENT`         | `MiniSearchEngine/1.0 (+educational-crawler)` | Custom HTTP User-Agent header                       |
| `REQUEST_TIMEOUT_S`  | `10.0`                                        | Per-request HTTP timeout in seconds                 |
| `POLITENESS_DELAY_S` | `1.0`                                         | Minimum delay between hits to the same domain       |
| `MAX_RETRIES`        | `3`                                           | Retries on transient HTTP failures (429/5xx)        |
| `RETRY_BACKOFF_S`    | `2.0`                                         | Base backoff multiplier for retries                 |
| `RESPECT_ROBOTS_TXT` | `True`                                        | Honor robots.txt exclusion rules                    |
| `MAX_PAGES`          | `500`                                         | Default maximum documents to crawl and store        |
| `MAX_DEPTH`          | `5`                                           | Maximum BFS depth from seeds                        |
| `MAX_LINKS_PER_PAGE` | `3`                                           | Maximum outbound links enqueued per page            |
| `SEED_FILE`          | `<project_root>/wl1/seeds.txt`                | Default seed list path                              |
| `DATA_DIR`           | `<project_root>/data`                         | Directory for persisted datasets                   |
| `CORPUS_PATH`        | `<project_root>/data/crawler.json`            | Default output corpus path                          |
| `CRAWLER_PATH`       | `<project_root>/data/crawler.json`            | Alias for `CORPUS_PATH`                             |
| `LOG_DIR`            | `<project_root>/logs`                         | Directory for crawl logs                            |
| `LOG_PATH`           | `<project_root>/logs/crawler.log`             | Default crawl log path                              |
| `STOPWORDS`          | frozen ~175 words                             | Self-contained set of lowercase English function words|

**Decision:** Stop-words are a self-contained `frozenset` of common English
function words, pronouns, auxiliaries, and contractions, normalized to alphanumeric
fragments so they match tokenizer output without requiring an external `nltk` dependency.

**Decision:** Dynamic root resolution (`_resolve_project_root()`) climbs parent
directories to locate `data/` and `.git` or `README.md`, ensuring path resolution
remains robust whether commands run from project root, `wl1/`, or test directories.

---

## 2. `wl1/crawler/models.py` — `Document`

**Purpose:** The immutable unit of persistence and the frozen join-key carrier for
Worklet 2 (indexing) and Worklet 3 (ranking).

```python
@dataclasses.dataclass(frozen=True)
class Document:
    doc_id: str                                  # "000001" (sequential "000XXX")
    url: str                                     # canonical page URL
    text: str                                    # visible text with SECTION_BREAK sentinels
    tokens: tuple[str, ...]                      # flat normalized token tuple (immutable)
    token_segments: tuple[tuple[str, ...], ...]  # per-block section tokens (immutable)
    meta: dict[str, Any]                         # crawled_at, content_length, status, depth
```

**Methods:**

- `to_dict() -> dict[str, Any]` — Generates the JSON-serializable record conforming
  to the frozen interface schema contract expected by Worklet 2. Converts `tokens`
  tuple → list and `token_segments` nested tuples → list of lists.
- `new_doc_id(seq: int = 1) -> str` — Formats sequential ID as `f"{int(seq):06d}"`
  (e.g., `"000001"`).
- `now_iso() -> str` — Current UTC ISO 8601 timestamp string (`YYYY-MM-DDTHH:MM:SSZ`).

**Decision:** `doc_id` is formatted as a 6-digit zero-padded sequential string
`"000XXX"` (e.g., `"000001"`), which can also be typecast to `int` in downstream C++ code.

**Decision:** `tokens` and `token_segments` are stored as tuples of tuples rather than
lists to uphold strict immutability under `frozen=True`.

**Decision (`token_segments`):** Preserves section boundaries from the parsed HTML.
Downstream phrase queries (Worklet 2) must only match words within the same structural
segment, preventing false phrase matches across layout boundaries (such as adjacent
footer columns or navigation items).

---

## 3. `wl1/crawler/frontier.py` — `URLFrontier`

**Purpose:** Enforce BFS ordering and prevent re-fetch loops using a FIFO
`collections.deque` and a `set` of canonicalized URLs.

**Public API:**

- `add(url) -> str | None` — Normalize and enqueue `url` if new; returns canonical
  URL or `None` if invalid, already visited, or disallowed by domain filters.
- `pop() -> str | None` — Pop next URL in FIFO order (`O(1)`).
- `empty() -> bool`, `__len__() -> int`, `visited -> set[str]` property.
- `normalize(url) -> str | None` — Static 5-step canonicalization pipeline.

**Normalization Pipeline:**

1. Scheme restricted to `http`/`https` (lowercased).
2. Fragment (`#...`) stripped.
3. Scheme and netloc lowercased.
4. Default ports (`:80`, `:443`) removed.
5. Empty path normalized to `/`; trailing slashes collapsed.

**Decision:** Optional `allowed_domains` filter restricts crawl boundaries to target
hosts. Returning canonical URL from `add()` lets `CrawlEngine` track BFS depth keyed
by canonical URL.

---

## 4. `wl1/crawler/fetcher.py` — `Fetcher`

**Purpose:** Retrieve raw HTML over HTTP/HTTPS with politeness and resilience.
Never raises exceptions to caller — malformed URLs, timeouts, and network errors are
logged and return `None`.

**Public API:**

- `fetch(url: str) -> str | None` — Fetch page HTML respecting robots.txt, politeness delays,
  and retrying retriable errors.
- `close() -> None` — Release underlying `requests.Session` and connection pools.

**Behavior:**

- `requests.Session` for persistent connection reuse.
- **Per-domain politeness:** Tracks `_last_request_time` as a `dict[str, float]` keyed by
  domain netloc, preventing delay interference between distinct domains.
- **Robots.txt compliance:** Uses `urllib.robotparser.RobotFileParser` cached per origin
  (`scheme://netloc`). Unreachable or missing `robots.txt` defaults to allowing access.
- **Transient retry with exponential backoff:** Retries statuses `{429, 500, 502, 503, 504}`
  and connection errors up to `MAX_RETRIES` (3) with `RETRY_BACKOFF_S * attempt` sleep.
- Skips unrecoverable pages by returning `None`.

---

## 5. `wl1/crawler/parser.py` — `parse_page` / `parse_html` / `extract_links`

**Purpose:** Turn raw HTML into clean visible text, section-break sentinels, and
outbound URLs using `lxml.html` (no `beautifulsoup4`).

**Key Exports & Constants:**

- `SECTION_BREAK = "\x00"` — Sentinel byte injected between block-level elements.
- `_BLOCK_TAGS` — Frozenset of HTML block/structural tags (`div`, `p`, `h1`-`h6`,
  `li`, `ul`, `ol`, `section`, `article`, `header`, `footer`, `table`, `td`, `th`, etc.).
- `parse_page(html, base_url) -> tuple[str, list[str]]` — **Single-pass**: parses DOM once,
  extracts absolute URLs from all `<a href>` tags, strips non-visible tags
  (`script`, `style`, `noscript`, `head`, `template`), and extracts collapsed text
  with `SECTION_BREAK` sentinels.
- `parse_html(html) -> str` — Extracts collapsed visible text with `SECTION_BREAK`
  sentinels between block elements.
- `extract_links(html, base_url) -> list[str]` — Collects absolute URLs resolved via
  `urllib.parse.urljoin`.

**Internal Helpers:**

- `_extract_text_with_breaks(node) -> str`: Recursively walks DOM tree, injecting
  `SECTION_BREAK` before and after block-level children while properly preserving inline
  elements (`<b>`, `<i>`, `<a>`, `<span>`) and tag `tail` text.
- `_collapse(raw) -> str`: Merges runs of whitespace and sentinels so that each boundary
  collapses to a clean `SECTION_BREAK` without extra spaces, and normal whitespace runs
  collapse to single spaces.
- `_parse_dom(html)`: Parses HTML with `lxml.html.fromstring`, handling malformed HTML
  gracefully by returning `None` instead of raising.

**Decision (Structural Boundary Isolation):** Words from different block elements
(such as separate footer links or header titles) are separated by `SECTION_BREAK`,
ensuring downstream tokenizers and phrase matching do not merge unrelated terms.

---

## 6. `wl1/crawler/tokenizer.py` — `tokenize` & `tokenize_segments`

**Purpose:** Token normalization and per-section segmentation pipeline.

**Public API:**

- `tokenize_segments(text: str | None) -> list[list[str]]` — Splits `text` on
  `SECTION_BREAK` sentinels into block fragments. Each fragment is tokenized:
  1. Regex `[a-zA-Z0-9]+` extracts alphanumeric words and strips punctuation in one pass.
  2. Lowercases tokens.
  3. Filters stop-words via `config.STOPWORDS`.
  Returns a list of token lists (one inner list per non-empty block segment).
- `tokenize(text: str | None) -> list[str]` — Flat interface. Calls `tokenize_segments(text)`
  and flattens all segments into a single list of tokens.

**Decision:** Retaining both segmented (`tokenize_segments`) and flat (`tokenize`)
interfaces allows backwards compatibility while providing the structural awareness
required for phrase search.

---

## 7. `wl1/crawler/store.py` — `JSONLStore`

**Purpose:** Append-only JSONL persistence, writing one document JSON record per line.

**Public API:**

- `append(document: Document) -> None` — Converts document via `to_dict()`, writes
  a UTF-8 JSON line, and immediately flushes the file handle.
- `close() -> None` — Closes the underlying file handle.
- Context manager support (`__enter__` / `__exit__`).

**Decision:** Immediate `flush()` after every record ensures crash resilience and
guarantees that an interrupted or partial crawl produces a valid, readable corpus
(`data/crawler.json`) ready for downstream processing.

---

## 8. `wl1/crawler/engine.py` — `CrawlEngine`

**Purpose:** Orchestrates the crawl feedback loop:
`pop URL -> fetch -> parse_page -> tokenize_segments -> persist Document -> enqueue links`.

**Constructor Parameters:**

```python
CrawlEngine(
    seeds: list[str],
    max_pages: int | None = None,           # default: config.MAX_PAGES (500)
    max_depth: int | None = None,           # default: config.MAX_DEPTH (5)
    max_links_per_page: int | None = None,  # default: config.MAX_LINKS_PER_PAGE (3)
    allowed_domains: list[str] | None = None,
    fetcher: Fetcher | None = None,
    store: JSONLStore | None = None,
    start_seq: int = 1,
)
```

**Key Execution Features:**

- **Single-Pass Parsing:** Uses `parse_page()` so HTML is parsed into DOM only once
  per crawled URL.
- **Segmented Tokenization:** Generates both flat `tokens` and structured `token_segments`
  stored on the `Document`.
- **Depth & Breadth Throttling:** Tracks BFS depth per normalized URL (`_depth: dict[str, int]`).
  If `depth < max_depth`, enqueues up to `max_links_per_page` outbound links per page,
  preventing crawler traps and exponential frontier explosion.
- **Resource Management:** `close()` cleanly releases both `JSONLStore` file handles
  and `Fetcher` HTTP session connection pools.

---

## 9. `wl1/main.py`

**Purpose:** CLI entry point for executing the crawler.

**Command-Line Options:**

| Flag                   | Default                     | Description                                         |
| ---------------------- | --------------------------- | --------------------------------------------------- |
| `--seeds`              | `wl1/seeds.txt`             | Seed URLs file (one per line, `#` comments allowed) |
| `--max-pages`          | `500`                       | Target document budget                              |
| `--max-depth`          | `5`                         | Maximum BFS crawl depth                             |
| `--max-links-per-page` | `3`                         | Maximum outbound links enqueued per page            |
| `--allowed-domains`    | `None`                      | Optional domain whitelist                           |
| `--corpus`, `--output` | `data/crawler.json`         | Destination path for crawled JSONL corpus           |
| `--log`                | `logs/crawler.log`          | Crawl log file path                                 |
| `--clear-corpus`       | `False` (flag)              | Deletes existing corpus file before starting crawl  |

**Usage Examples:**

```bash
# Run from repository root
python wl1/main.py --seeds wl1/seeds.txt --max-pages 500

# Or execute inside wl1/
cd wl1
python main.py --seeds seeds.txt --max-pages 500 --clear-corpus
```

---

## 10. `wl1/crawler/__init__.py` — Package Exports

The `crawler` package exposes the following clean public interface:

```python
from crawler import (
    Document,
    URLFrontier,
    Fetcher,
    parse_html,
    extract_links,
    parse_page,
    SECTION_BREAK,
    tokenize,
    tokenize_segments,
    JSONLStore,
    CrawlEngine,
)
```

---

## Design Decisions Summary

| Decision                            | Rationale                                                               |
| ----------------------------------- | ----------------------------------------------------------------------- |
| `lxml` (not `beautifulsoup4`)       | Fast, memory-efficient C-based parser with robust handling of malformed HTML |
| Built-in stopwords (not `nltk`)     | Avoids ~70 MB external dependency and runtime download requirements    |
| JSONL corpus (`data/crawler.json`)  | Streamable, `grep`-friendly, append-safe, easily ingested by C++ in W2 |
| Sequential `doc_id` (`000XXX`)      | Conforms to W2/W3 spec contract; predictable IDs (`000001`...) typecastable to integer |
| Section-break sentinel (`\x00`)     | Separates block-level HTML tags during text extraction to prevent false phrase matches across layout elements |
| `token_segments` in `Document`      | Explicitly provides block-level token boundaries to W2 inverted index for accurate phrase queries |
| `tuple` tokens on frozen dataclass  | Enforces true immutability on `Document` instances                     |
| Single-pass `parse_page()`          | Avoids re-parsing DOM twice in the crawl loop                           |
| Depth & link throttling             | `max_depth` (5) and `max_links_per_page` (3) prevent crawler traps and frontier explosion |
| Per-domain politeness & robots.txt  | Polite crawling without blocking unrelated domains                      |
| `is not None` parameter defaults    | Allows `0` as an explicit parameter value (e.g., zero delay or zero max pages) |
| Dynamic root via `pathlib`          | Portable execution regardless of caller's current working directory     |

---

## Testing

Pytest suite located under `tests/wl1/` links to the package via `conftest.py`:

```
tests/wl1/
├── __init__.py          # package marker
├── conftest.py          # adds wl1/ directory to sys.path
├── test_fetcher.py      # mocked HTTP status codes, politeness delay, retry backoff, robots.txt
├── test_frontier.py     # 5-step URL normalization, deduplication, domain filter
├── test_parser.py       # visible text extraction, link resolution, malformed HTML, section breaks
├── test_store.py        # JSONL append, schema validation, tokens & token_segments serialization
└── test_tokenizer.py    # lowercasing, punctuation stripping, stopwords, tokenize_segments
```

Run test suite:

```bash
pytest
```
