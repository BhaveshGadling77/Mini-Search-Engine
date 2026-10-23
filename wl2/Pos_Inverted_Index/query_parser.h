#ifndef QUERY_PARSER_H
#define QUERY_PARSER_H
#include "../Inverted_Index/CorpusReader.h"
#include <string>
#include <unordered_map>
#include <vector>
inline constexpr int STOPWORDS_ONLY_SENTINEL_DOC_ID = -1;
using QueryCandidates = std::unordered_map<int, std::unordered_map<std::string, int>>;
using DocumentFrequency = std::unordered_map<std::string, int>;
struct QueryResult {
    QueryCandidates candidates;
    DocumentFrequency doc_freq;
};
struct CorpusStats {
    int total_docs = 0;
    double avg_doc_length = 0;
};
struct DocSnippetData {
    std::string title, url, text;
};
void initialize_query_processor(const std::vector<Document> *documents);
QueryResult resolve_query(const std::string &query_string);
CorpusStats get_corpus_stats();
std::string get_index_version();
std::unordered_map<int, DocSnippetData> get_doc_snippet_data(const std::vector<int> &ids);
std::unordered_map<int, std::unordered_map<std::string, int>>
get_doc_terms(const std::vector<int> &ids);
#endif
