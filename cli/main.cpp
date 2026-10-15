#include "../wl2/Inverted_Index/CorpusReader.h"
#include "../wl2/Pos_Inverted_Index/query_parser.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    const std::string corpus = argc > 1 ? argv[1] : "data/crawler.json";
    auto docs = readDocuments(corpus);
    if (docs.empty()) { std::cerr << "No documents loaded from " << corpus << "\n"; return 1; }
    initialize_query_processor(&docs);
    const auto stats = get_corpus_stats();
    std::cout << "Mini Search Engine — " << stats.total_docs << " documents. Type :quit to exit.\n";
    std::string query;
    while (std::cout << "search> " && std::getline(std::cin, query)) {
        if (query == ":quit" || query == ":q" || query == "exit") break;
        if (query.empty()) continue;
        try {
            auto result = resolve_query(query);
            struct Hit { int id; double score; };
            std::vector<Hit> hits;
            for (const auto& candidate : result.candidates) {
                double score = 0;
                for (const auto& term : candidate.second) {
                    const int df = result.doc_freq[term.first];
                    const double idf = std::log(1.0 + (stats.total_docs - df + 0.5) / (df + 0.5));
                    score += idf * term.second;
                }
                hits.push_back({candidate.first, score});
            }
            std::sort(hits.begin(), hits.end(), [](const Hit&a,const Hit&b){return a.score>b.score;});
            if (hits.empty()) { std::cout << "No matches.\n"; continue; }
            std::vector<int> ids; for (size_t i=0;i<std::min<size_t>(10,hits.size());++i) ids.push_back(hits[i].id);
            const auto snippets=get_doc_snippet_data(ids);
            for(size_t i=0;i<ids.size();++i){const auto& d=snippets.at(ids[i]);std::cout<<i+1<<". ["<<ids[i]<<"] "<<(d.title.empty()?"(untitled)":d.title)<<"  score="<<hits[i].score<<"\n   "<<d.url<<"\n   "<<d.text.substr(0,240)<<"\n";}
        } catch (const std::exception& e) { std::cout << "Query error: " << e.what() << "\n"; }
    }
}
