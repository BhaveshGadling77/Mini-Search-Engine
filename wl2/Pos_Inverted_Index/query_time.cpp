#include "query_parser.h"
#include <chrono>
#include <iomanip>
#include <iostream>
#include <vector>

int main() {
    const std::vector<Document> documents = readDocuments("data/crawler.json");
    if (documents.empty()) {
        std::cerr << "Could not load data/crawler.json\n";
        return 1;
    }

    initialize_query_processor(&documents);

    const std::vector<std::pair<std::string, std::string>> queries = {
        {"Single Word", "python"},
        {"Phrase", "\"python tutorial\""},
        {"Boolean AND", "python AND tutorial"},
        {"Boolean OR", "python OR rust"},
        {"Boolean NOT", "NOT rust"},
        {"Wildcard", "py*"},
    };

    for (const auto &[type, query] : queries) {
        const auto start = std::chrono::steady_clock::now();
        const QueryResult result = resolve_query(query);
        const auto end = std::chrono::steady_clock::now();
        const double elapsed_ms =
            std::chrono::duration<double, std::milli>(end - start).count();
        std::cout << "Query type: " << type << ", Query: " << query
                  << ", Time: " << std::fixed << std::setprecision(3)
                  << elapsed_ms << " ms\n";
    }

    return 0;
}