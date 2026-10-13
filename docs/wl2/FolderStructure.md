```text
Mini-Search-Engine/
│
├── crawler/
│   ├── Crawler
│   ├── URLFrontier
│   ├── Fetcher
│   ├── HTMLParser
│   ├── TokenizerNormalizer
│   ├── Document
│   └── FileStore
│
├── index/
│   ├── CorpusReader
│   ├── InvertedIndex
│   ├── PostingList
│   ├── Posting
│   ├── Trie
│   ├── QueryParser
│   ├── QueryProcessor
│   └── PostingsOperations
│
├── ranking/
│   ├── QueryEngine
│   ├── Ranker
│   ├── RankedResult
│   └── TopKRetriever
│
├── cache/
│   ├── CacheManager
│   ├── LRUCache
│   └── SQLiteCache
│
├── cli/
│   └── REPL
│
├── evaluation/
│   ├── PrecisionRecall
│   └── Latency
│
├── tests/
└── docs/
```

This is just a 