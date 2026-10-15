#include "../wl2/Inverted_Index/CorpusReader.h"
#include "../wl2/Pos_Inverted_Index/query_parser.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

static std::string lowercase(std::string value) {
    for (char &c : value)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return value;
}

static std::string displayTitle(const DocSnippetData &doc) {
    if (!doc.title.empty())
        return doc.title;
    std::string host = doc.url;
    const size_t scheme = host.find("://");
    if (scheme != std::string::npos)
        host.erase(0, scheme + 3);
    const size_t slash = host.find('/');
    if (slash != std::string::npos)
        host.resize(slash);
    if (host.rfind("www.", 0) == 0)
        host.erase(0, 4);
    return host.empty() ? "(untitled)" : host;
}

static std::string relevantSnippet(const std::string &text,
                                   const std::unordered_map<std::string, int> &queryTerms) {
    constexpr size_t width = 240;
    if (text.size() <= width)
        return text;
    const std::string folded = lowercase(text);
    size_t match = std::string::npos;
    for (const auto &term : queryTerms) {
        const size_t found = folded.find(lowercase(term.first));
        if (found != std::string::npos && (match == std::string::npos || found < match))
            match = found;
    }
    size_t start = match == std::string::npos || match < 80 ? 0 : match - 80;
    if (start > 0) {
        const size_t boundary = text.find(' ', start);
        if (boundary != std::string::npos && boundary < start + 20)
            start = boundary + 1;
    }
    size_t end = std::min(text.size(), start + width);
    if (end < text.size()) {
        const size_t boundary = text.rfind(' ', end);
        if (boundary != std::string::npos && boundary > end - 20)
            end = boundary;
    }
    return (start ? "…" : "") + text.substr(start, end - start) + (end < text.size() ? "…" : "");
}

int main(int argc, char **argv) {
    const std::string corpus = argc > 1 ? argv[1] : "data/crawler.json";
    auto docs = readDocuments(corpus);
    if (docs.empty()) {
        std::cerr << "No documents loaded from " << corpus << "\n";
        return 1;
    }
    initialize_query_processor(&docs);
    const auto stats = get_corpus_stats();
    std::cout << "Mini Search Engine -- " << stats.total_docs
              << " documents. Type :quit to exit.\n";
    std::string query;
    while (std::cout << "search> " && std::getline(std::cin, query)) {
        if (query == ":quit" || query == ":q" || query == "exit")
            break;
        if (query.empty())
            continue;
        try {
            auto result = resolve_query(query);
            struct Hit {
                int id;
                double score;
            };
            std::vector<Hit> hits;
            for (const auto &candidate : result.candidates) {
                double score = 0;
                for (const auto &term : candidate.second) {
                    const int df = result.doc_freq[term.first];
                    const double idf = std::log(1.0 + (stats.total_docs - df + 0.5) / (df + 0.5));
                    score += idf * term.second;
                }
                hits.push_back({candidate.first, score});
            }
            std::sort(hits.begin(), hits.end(),
                      [](const Hit &a, const Hit &b) { return a.score > b.score; });
            if (hits.empty()) {
                std::cout << "No matches.\n";
                continue;
            }
            std::vector<int> ids;
            for (size_t i = 0; i < std::min<size_t>(10, hits.size()); ++i)
                ids.push_back(hits[i].id);
            const auto snippets = get_doc_snippet_data(ids);
            for (size_t i = 0; i < ids.size(); ++i) {
                const auto &d = snippets.at(ids[i]);
                const auto &queryTerms = result.candidates.at(ids[i]);
                std::cout << i + 1 << ". [" << ids[i] << "] " << displayTitle(d)
                          << "  score=" << hits[i].score << "\n   " << d.url << "\n   "
                          << relevantSnippet(d.text, queryTerms) << "\n";
            }
        } catch (const std::exception &e) {
            std::cout << "Query error: " << e.what() << "\n";
        }
    }
}
