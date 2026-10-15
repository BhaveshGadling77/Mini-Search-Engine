
#include "query_parser.h"
#include <iostream>

int main()
{
    std::vector<Document> documents =
        readDocuments("wl2/Pos_Inverted_Index/sample_input.json");

    HashMap index;

    initialize_query_processor(&index, &documents);

    std::cout << "Mini Search Engine Query Tester\n";
    std::cout << "Documents loaded: "
              << get_corpus_stats().total_docs << "\n\n";

    std::string query;

    while (true)
    {
        std::cout << "Enter query (type exit to quit): ";

        if (!std::getline(std::cin, query))
            break;

        if (query == "exit")
            break;

        QueryResult result = resolve_query(query);

        std::cout << "Matching documents: "
                  << result.candidates.size() << '\n';

        for (const auto& doc : result.candidates)
        {
            std::cout << "Document ID: " << doc.first << '\n';

            for (const auto& term : doc.second)
            {
                std::cout << "  " << term.first
                          << ": " << term.second << '\n';
            }
        }

        std::cout << '\n';
    }

    return 0;
}
