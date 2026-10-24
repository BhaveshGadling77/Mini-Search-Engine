#include "CorpusReader.h"
#include "query_parser.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <chrono>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

static std::string lowercase(std::string value) {
    for (char &c : value)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return value;
}

static std::string sanitize_for_terminal(const std::string &s) {
    std::string out;
    out.reserve(s.size());
    for (unsigned char ch : s) {
        if (ch == '\0')
            out.push_back(' ');
        else if (ch == '\n' || ch == '\r' || ch == '\t')
            out.push_back(static_cast<char>(ch));
        else if (ch >= 0x20 && ch < 0x7F)
            out.push_back(static_cast<char>(ch));
        else if ((ch & 0x80) != 0)
            out.push_back(static_cast<char>(ch));
        else
            out.push_back('?');
    }
    return out;
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
    constexpr size_t width = 180;
    if (text.size() <= width)
        return sanitize_for_terminal(text);
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
    std::string snippet = (start ? "…" : "") + text.substr(start, end - start) + (end < text.size() ? "…" : "");
    return sanitize_for_terminal(snippet);
}

static void print_wrapped(const std::string &s, size_t width = 80) {
    std::string clean = sanitize_for_terminal(s);
    size_t i = 0;
    while (i < clean.size()) {
        size_t end = std::min(i + width, clean.size());
        if (end < clean.size()) {
            size_t boundary = clean.rfind(' ', end);
            if (boundary != std::string::npos && boundary > i + width / 2)
                end = boundary;
        }
        std::cout << clean.substr(i, end - i);
        i = end;
        while (i < clean.size() && clean[i] == ' ')
            ++i;
        if (i < clean.size())
            std::cout << "\n";
    }
}

int main(int argc, char **argv) {
    const std::string corpus = argc > 1 ? argv[1] : "./data/crawler.json";
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
        const auto query_start = std::chrono::steady_clock::now();
        try {
            auto result = resolve_query(query);
            struct Hit {
                int id;
                double score;
            };
            std::vector<Hit> hits;
            for (const auto &candidate : result.candidates) {
                if (candidate.first == STOPWORDS_ONLY_SENTINEL_DOC_ID)
                    continue;
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
                const auto elapsed = std::chrono::duration<double, std::milli>(
                    std::chrono::steady_clock::now() - query_start).count();
                std::cout << "Query time: " << elapsed << " ms\n";
                continue;
            }
            std::vector<int> ids;
            for (size_t i = 0; i < hits.size(); ++i)
                ids.push_back(hits[i].id);
            const auto snippets = get_doc_snippet_data(ids);
            const auto elapsed = std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() - query_start).count();
            for (size_t i = 0; i < ids.size(); ++i) {
                const auto &d = snippets.at(ids[i]);
                const auto &queryTerms = result.candidates.at(ids[i]);
                std::cout << i + 1 << ". [" << ids[i] << "] " << displayTitle(d)
                          << "  score=" << hits[i].score << "\n   " << d.url << "\n";
                print_wrapped(relevantSnippet(d.text, queryTerms), 80);
                std::cout << "\n";
            }
            std::cout << "Query time: " << elapsed << " ms\n";
        } catch (const std::exception &e) {
            std::cout << "Query error: " << e.what() << "\n";
            const auto elapsed = std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() - query_start).count();
            std::cout << "Query time: " << elapsed << " ms\n";
        }
    }
    return 0;
}
