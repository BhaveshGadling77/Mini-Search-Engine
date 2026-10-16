#include "../../wl2/Inverted_Index/CorpusReader.h"
#include "../../wl2/Pos_Inverted_Index/query_parser.h"
#include <cassert>
#include <fstream>
#include <iostream>
int main() {
    const char *path = "/tmp/mini_search_bridge_test.jsonl";
    {
        std::ofstream f(path);
        f << R"({"doc_id":"1","title":"Alpha page","url":"https://a.test","text":"red fox jumps","tokens":["red","fox","jumps"]})"
          << '\n';
        f << R"({"doc_id":"2","title":"Blue page","url":"https://b.test","text":"red dog","tokens":["red","dog"]})"
          << '\n';
    }
    auto docs = readDocuments(path);
    assert(docs.size() == 2);
    assert(docs[0].url == "https://a.test");
    initialize_query_processor(&docs);
    auto stats = get_corpus_stats();
    assert(stats.total_docs == 2 && stats.avg_doc_length == 2.5);
    auto q = resolve_query("red");
    assert(q.candidates.size() == 2 && q.doc_freq["red"] == 2);
    q = resolve_query("\"red fox\"");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    q = resolve_query("red AND fox");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    q = resolve_query("fox OR dog");
    assert(q.candidates.size() == 2);
    q = resolve_query("\"red fox\" AND jumps");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    q = resolve_query("\"red fox jumps\"");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    q = resolve_query("\"red jumps\"");
    assert(q.candidates.empty());
    q = resolve_query("\"red fox\" OR \"red dog\"");
    assert(q.candidates.size() == 2);
    q = resolve_query("red fox AND jumps");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    q = resolve_query("f*x AND \"red fox\"");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    q = resolve_query("NOT dog");
    assert(q.candidates.size() == 1 && q.candidates.count(1));
    auto details = get_doc_snippet_data({1});
    assert(details.at(1).title == "Alpha page" && details.at(1).text == "red fox jumps");
    auto terms = get_doc_terms({1});
    assert(terms.at(1).at("fox") == 1 && terms.at(1).size() == 3);
    assert(!get_index_version().empty());
    std::remove(path);
    std::cout << "Worklet 2 bridge tests passed\n";
}
