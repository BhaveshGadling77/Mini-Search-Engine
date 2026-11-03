#include "../../wl2/lib/src/include/text_processing.h"
#include <iostream>
#include <string>
#include <vector>

int main() {
    const std::vector<std::vector<std::string>> groups = {
        {"running", "runs", "ran", "run"},
        {"children", "child"},
        {"better", "best", "good"},
        {"mice", "mouse"},
        {"search", "searching","searched","searches"}
    };

    std::cout << "Lemmatization demo\n";
    std::cout << "==================\n";

    for (size_t i = 0; i < groups.size(); ++i) {
        const auto &group = groups[i];
        std::vector<std::string> lemmas;
        for (const auto &word : group) {
            lemmas.push_back(wl2::lemmatize(word));
        }

        std::cout << "Set " << (i + 1) << ": ";
        for (size_t j = 0; j < group.size(); ++j) {
            if (j > 0) std::cout << ", ";
            std::cout << group[j] << " -> " << lemmas[j];
        }
        std::cout << "\n";
        std::cout << "Common lemma: " << lemmas[0] << "\n\n";
    }

    return 0;
}
