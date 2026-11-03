#include "../../wl2/Inverted_Index/CorpusReader.h"
#include "../../wl2/Pos_Inverted_Index/query_parser.h"
#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    const std::string corpus = argc > 1 ? argv[1] : "./data/crawler.json";
    auto docs = readDocuments(corpus);
    if (docs.empty()) {
        std::cerr << "No documents loaded from " << corpus << "\n";
        return 1;
    }

    initialize_query_processor(&docs);

    const std::vector<std::string> patterns = {"pre*", "*ent", "pre*ent", "*nac*"};
    std::cout << "Loaded corpus: " << corpus << "\n";
    std::cout << "Searching trie patterns with lemmatized vocabulary matches:\n";

    for (const auto &pattern : patterns) {
        auto matches = expand_wildcard_terms(pattern);
        std::sort(matches.begin(), matches.end());
        std::cout << "\nPattern: " << pattern << "\n";
        if (matches.empty()) {
            std::cout << "  (no eligible words)\n";
            continue;
        }
        for (const auto &term : matches) {
            std::cout << "  " << term << "\n";
        }
    }

    return 0;
}
