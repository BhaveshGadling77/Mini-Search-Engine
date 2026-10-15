#ifndef QUERY_PARSER_H
#define QUERY_PARSER_H

#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>

// Worklet 2 headers
#include "HashMap.h"
#include "JsonReader.h"
#include "../trie/trie.h"
using namespace std;

using QueryCandidates =
    unordered_map<int, unordered_map<string, int>>;

using DocumentFrequency =
    unordered_map<string, int>;

struct QueryResult
{
    QueryCandidates candidates;
    DocumentFrequency doc_freq;
};

struct CorpusStats
{
    int total_docs = 0;
    double avg_doc_length = 0.0;
};

struct DocSnippetData
{
    string title;
    string url;
    string text;
};

void initialize_query_processor(
    HashMap* index,
    const vector<Document>* documents,
    Trie* prefix_trie = nullptr,
    Trie* reversed_suffix_trie = nullptr
);

QueryResult resolve_query(const string& query_string);

CorpusStats get_corpus_stats();

string get_index_version();

unordered_map<int, DocSnippetData>
get_doc_snippet_data(const vector<int>& doc_ids);

unordered_map<int, unordered_map<string, int>>
get_doc_terms(const vector<int>& doc_ids);

#endif