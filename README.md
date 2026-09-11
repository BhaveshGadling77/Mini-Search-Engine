# Mini Search Engine

A compact search engine built from scratch to understand the core workflow behind search systems — from collecting and processing documents to indexing, querying, ranking, and evaluating search results.

The project is intentionally **foundation-focused**. Instead of relying on existing search engines or search libraries, the major components are implemented from the ground up.

---

## Overview

The Mini Search Engine works with a small collection of local or simulated web pages.

It follows a simple pipeline:

**Crawl → Process → Index → Query → Rank → Cache → Evaluate**

The system is designed to support different types of searches, including:

* Boolean queries
* Phrase queries
* Prefix searches
* Wildcard searches
* Ranked searches

It also provides an interactive command-line interface and allows the performance and quality of the search engine to be evaluated using metrics such as precision, recall, and query latency.

---

## Project Structure

The project is divided into three worklets, with each worklet responsible for a specific part of the search pipeline.

### Worklet 1 — Crawler & Document Model

**Responsibility:** Collecting and preparing documents for the search engine.

Worklet 1 handles the initial stage of the project. It is responsible for:

* Crawling a small collection of local or simulated web pages.
* Fetching pages and extracting their useful content.
* Discovering links between pages.
* Cleaning and preparing extracted text.
* Tokenizing and normalizing document content.
* Preparing documents in a format that can be consumed by the indexing stage.
* Persisting the processed documents and their metadata.

**Output:** A clean and processed collection of documents ready to be indexed.

---

### Worklet 2 — Inverted Index & Query Processing

**Responsibility:** Building the searchable index and processing search queries.

Worklet 2 is implemented **entirely in C++** and does not use external search libraries or additional modules for its implementation.

It is responsible for:

* Building the search index from the processed documents.
* Making document content searchable.
* Processing Boolean queries such as `AND`, `OR`, and `NOT`.
* Supporting phrase queries.
* Supporting prefix searches.
* Supporting wildcard searches.
* Retrieving documents that match a given query.
* Performing efficient query-result processing.

**Output:** A C++ query-processing component capable of retrieving documents for different types of search queries.

---

### Worklet 3 — Ranking, Caching & Evaluation

**Responsibility:** Ranking search results and evaluating the search engine.

Worklet 3 takes the results produced by the query-processing stage and makes them useful to the user.

It is responsible for:

* Ranking matching documents according to their relevance.
* Implementing a relevance-ranking method such as TF-IDF or BM25.
* Returning the most relevant top-k results.
* Providing an interactive CLI/REPL for submitting queries.
* Highlighting relevant terms in search results.
* Caching repeated queries.
* Measuring query latency and search performance.
* Evaluating search quality using precision and recall.

**Output:** A usable search interface that returns ranked results and provides measurable search quality and performance.

---

## Worklet Responsibilities

| Worklet       | Responsibility                                                                     |
| ------------- | ---------------------------------------------------------------------------------- |
| **Worklet 1** | Collect and prepare the document corpus                                            |
| **Worklet 2** | Build the searchable index and process queries in C++                              |
| **Worklet 3** | Rank results, provide the search interface, cache queries, and evaluate the system |

### Overall Flow

```text
        Documents / Web Pages
                │
                ▼
      ┌───────────────────┐
      │     Worklet 1     │
      │ Crawler & Document │
      │      Model         │
      └─────────┬─────────┘
                │
                ▼
      ┌───────────────────┐
      │     Worklet 2     │
      │ Index & Query      │
      │   Processing       │
      │      (C++)         │
      └─────────┬─────────┘
                │
                ▼
      ┌───────────────────┐
      │     Worklet 3     │
      │ Ranking, Cache &   │
      │    Evaluation      │
      └─────────┬─────────┘
                │
                ▼
          Ranked Results
```

---

## Project Goal

The goal of this project is to understand how a search engine works internally by building its core components ourselves.

By completing the three worklets, the project covers the complete journey from:

**Raw Documents → Searchable Content → Query Results → Ranked Results**

The emphasis is on understanding the fundamentals rather than depending on pre-built search solutions.

---

## Scope

The project is designed as a **small-scale educational search engine**. It focuses on the core search pipeline and intentionally avoids databases, web frameworks, cloud services, and machine-learning-based search solutions.

The final system should be small enough to understand completely while still demonstrating the major stages involved in building a basic search engine.
