#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "CorpusReader.h"
#include "Inverted_Index.h"

int main() {
    std::vector<std::string> possiblePaths = {
        "./data/crawler.json",
        "./wl2/Inverted_Index/crawler.json",
        "./crawler.json"
    };

    std::string corpus;
    for (const auto &path : possiblePaths) {
        std::ifstream test(path);
        if (test) {
            corpus = path;
            break;
        }
    }

    if (corpus.empty()) {
        std::cout << "No corpus file found.\n";
        return 1;
    }

    std::vector<Document> docs = readDocuments(corpus);

    if (docs.empty()) {
        std::cout << "No documents found in " << corpus << ".\n";
        return 1;
    }

    Inverted_Index index;
    const double elapsed = index.measureStorageTimeMs(docs);

    std::cout << "Corpus stored in the Inverted Index in " << elapsed << " ms\n";
    return 0;
}
