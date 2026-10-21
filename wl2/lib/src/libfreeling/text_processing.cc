#include "../include/text_processing.h"

#include <algorithm>
#include <cctype>
#include <unordered_map>
#include <unordered_set>

namespace wl2 {
std::string normalize_token(const std::string &token) {
    std::string result;
    result.reserve(token.size());
    for (unsigned char c : token)
        result.push_back(static_cast<char>(std::tolower(c)));
    return result;
}

bool is_stopword(const std::string &raw) {
    static const std::unordered_set<std::string> words = {
        "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
        "for", "from", "had", "has", "have", "he", "her", "hers", "him", "his",
        "i", "if", "in", "into", "is", "it", "its", "me", "my", "of", "on", "or",
        "our", "ours", "she", "so", "that", "the", "their", "them", "then", "there",
        "these", "they", "this", "those", "to", "was", "we", "were", "what", "when",
        "where", "which", "who", "will", "with", "you", "your"};
    return words.count(normalize_token(raw)) != 0;
}

std::string lemmatize(const std::string &raw) {
    std::string word = normalize_token(raw);
    static const std::unordered_map<std::string, std::string> irregular = {
        {"am", "be"}, {"is", "be"}, {"are", "be"}, {"was", "be"}, {"were", "be"},
        {"has", "have"}, {"had", "have"}, {"does", "do"}, {"did", "do"},
        {"went", "go"}, {"gone", "go"}, {"better", "good"}, {"best", "good"},
        {"children", "child"}, {"men", "man"}, {"women", "woman"}, {"mice", "mouse"},
        {"geese", "goose"}, {"teeth", "tooth"}, {"feet", "foot"}, {"ran", "run"}};
    const auto found = irregular.find(word);
    if (found != irregular.end()) return found->second;
    if (word.size() > 5 && word.compare(word.size() - 3, 3, "ies") == 0)
        return word.substr(0, word.size() - 3) + "y";
    if (word.size() > 5 && word.compare(word.size() - 3, 3, "ing") == 0) {
        word.erase(word.size() - 3);
        if (word.size() > 2 && word.back() == word[word.size() - 2]) word.pop_back();
        return word;
    }
    if (word.size() > 4 && word.compare(word.size() - 2, 2, "ed") == 0) {
        word.erase(word.size() - 2);
        if (word.size() > 2 && word.back() == word[word.size() - 2]) word.pop_back();
        return word;
    }
    if (word.size() > 4 && word.compare(word.size() - 2, 2, "es") == 0)
        return word.substr(0, word.size() - 2);
    if (word.size() > 3 && word.back() == 's' && word.compare(word.size() - 2, 2, "ss") != 0)
        word.pop_back();
    return word;
}

std::vector<std::string> tokenize(const std::string &text) {
    std::vector<std::string> words;
    std::string current;
    for (unsigned char c : text) {
        if (std::isalnum(c) || c == '_' || c == '*') current.push_back(static_cast<char>(c));
        else if (!current.empty()) { words.push_back(normalize_token(current)); current.clear(); }
    }
    if (!current.empty()) words.push_back(normalize_token(current));
    return words;
}

std::vector<std::string> process_text(const std::string &text) {
    std::vector<std::string> result;
    for (const auto &word : tokenize(text))
        if (!is_stopword(word))
            result.push_back(word.find('*') == std::string::npos ? lemmatize(word) : word);
    return result;
}
} // namespace wl2
