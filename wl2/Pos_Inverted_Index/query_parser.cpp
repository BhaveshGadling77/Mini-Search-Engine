#include "query_parser.h"
#include "../Inverted_Index/Inverted_Index.h"
#include "../boolean_operations/PostingsOperations.h"
#include "../trie/trie.h"
#include "../lib/src/include/text_processing.h"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <iterator>
#include <set>
#include <stdexcept>
#include <memory>
#include <utility>

namespace {
const std::vector<Document> *docs = nullptr;
std::unordered_map<int, std::unordered_map<std::string, int>> terms;
std::unordered_map<std::string, int> df;
std::unique_ptr<Inverted_Index> inverted_index;
std::unique_ptr<Trie> vocabulary_trie;
std::string version = "uninitialized";

std::string normalize(std::string value) {
    for (char &c : value)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return value;
}

bool trie_word(const std::string &word) {
    return !word.empty() && std::all_of(word.begin(), word.end(), [](unsigned char c) {
        return c >= 'a' && c <= 'z';
    });
}

bool wildcard_matches(const std::string &value, const std::string &pattern) {
    const std::string normalized_value = normalize(value);
    const std::string normalized_pattern = normalize(pattern);
    size_t value_index = 0;
    size_t pattern_index = 0;
    size_t star_index = std::string::npos;
    size_t value_match = 0;
    while (value_index < normalized_value.size()) {
        if (pattern_index < normalized_pattern.size() && normalized_pattern[pattern_index] == '*') {
            star_index = pattern_index;
            value_match = value_index;
            ++pattern_index;
        } else if (pattern_index < normalized_pattern.size() &&
                   normalized_pattern[pattern_index] == normalized_value[value_index]) {
            ++pattern_index;
            ++value_index;
        } else if (star_index != std::string::npos) {
            pattern_index = star_index + 1;
            ++value_match;
            value_index = value_match;
        } else {
            return false;
        }
    }
    while (pattern_index < normalized_pattern.size() && normalized_pattern[pattern_index] == '*')
        ++pattern_index;
    return pattern_index == normalized_pattern.size();
}

std::vector<std::string> split_words(const std::string &input) {
    return wl2::process_text(input);
}

std::string document_text(const Document &doc) {
    if (!doc.text.empty())
        return doc.text;
    std::string text;
    for (const auto &token : doc.tokens) {
        if (!text.empty())
            text += ' ';
        text += token;
    }
    return text;
}

const Document *find_document(int id) {
    if (!docs)
        return nullptr;
    const auto found = std::find_if(docs->begin(), docs->end(),
                                    [id](const Document &doc) { return doc.docId == id; });
    return found == docs->end() ? nullptr : &*found;
}

std::vector<std::string> canonicalize_trie_matches(const std::vector<std::string> &matches) {
    std::set<std::string> seen;
    std::vector<std::string> result;
    for (const auto &match : matches) {
        const auto lemma = wl2::lemmatize(normalize(match));
        if (lemma.empty() || !seen.insert(lemma).second)
            continue;
        result.push_back(lemma);
    }
    return result;
}

std::vector<std::string> dictionary_expansion(const std::string &pattern) {
    std::vector<std::string> result;
    if (pattern.find('*') == std::string::npos) {
        if (df.count(pattern))
            result.push_back(pattern);
        return result;
    }
    for (const auto &entry : df)
        if (wildcard_matches(entry.first, pattern))
            result.push_back(entry.first);
    result.erase(std::remove_if(result.begin(), result.end(), [&](const auto &term) { return !df.count(term); }), result.end());
    std::sort(result.begin(), result.end());
    return result;
}

std::vector<std::string> trie_expansion(const std::string &pattern) {
    if (pattern.find('*') == std::string::npos) {
        return df.count(pattern) ? std::vector<std::string>{pattern} : std::vector<std::string>{};
    }
    if (!vocabulary_trie || !std::all_of(pattern.begin(), pattern.end(), [](unsigned char c) {
            return std::isalpha(c) || c == '*';
        })) {
        return dictionary_expansion(pattern);
    }

    const size_t star_count = std::count(pattern.begin(), pattern.end(), '*');
    if (star_count == 1) {
        const size_t star = pattern.find('*');
        const auto prefix = pattern.substr(0, star), suffix = pattern.substr(star + 1);
        if ((!prefix.empty() && !trie_word(prefix)) || (!suffix.empty() && !trie_word(suffix)))
            return dictionary_expansion(pattern);

        std::vector<std::string> result;
        if (prefix.empty() && suffix.empty()) {
            for (const auto &entry : df)
                result.push_back(entry.first);
            return canonicalize_trie_matches(result);
        }
        if (!prefix.empty() && !suffix.empty())
            result = vocabulary_trie->searchForWildCard(prefix, suffix);
        else if (!prefix.empty())
            result = vocabulary_trie->searchForPrefix(prefix);
        else if (!suffix.empty())
            result = vocabulary_trie->searchForSuffix(suffix);
        return canonicalize_trie_matches(result);
    }

    if (star_count >= 2) {
        const auto first_star = pattern.find('*');
        const auto second_star = pattern.find('*', first_star + 1);
        const auto prefix = pattern.substr(0, first_star);
        const auto infix = pattern.substr(first_star + 1, second_star - first_star - 1);
        const auto suffix = pattern.substr(second_star + 1);

        std::vector<std::string> candidates;
        if (prefix.empty() && suffix.empty() && !infix.empty() && trie_word(infix)) {
            candidates = vocabulary_trie->searchForInfixWildCard(infix);
        } else {
            if (!prefix.empty() && trie_word(prefix)) {
                candidates = vocabulary_trie->searchForPrefix(prefix);
            } else if (!infix.empty() && trie_word(infix)) {
                candidates = vocabulary_trie->searchForInfixWildCard(infix);
            } else if (!suffix.empty() && trie_word(suffix)) {
                candidates = vocabulary_trie->searchForSuffix(suffix);
            } else {
                return dictionary_expansion(pattern);
            }
        }

        std::vector<std::string> result;
        for (const auto &term : candidates)
            if (wildcard_matches(term, pattern))
                result.push_back(term);
        return canonicalize_trie_matches(result);
    }

    return dictionary_expansion(pattern);
}

std::vector<std::string> terms_for_document(const Document &doc) {
    return split_words(document_text(doc));
}

std::vector<std::string> document_tokens(const Document &doc) {
    if (!doc.text.empty())
        return wl2::tokenize(doc.text);
    std::vector<std::string> tokens;
    tokens.reserve(doc.tokens.size());
    for (const auto &token : doc.tokens)
        tokens.push_back(normalize(token));
    return tokens;
}

std::vector<std::vector<std::string>> sentence_tokens_for_document(const Document &doc) {
    std::vector<std::vector<std::string>> sentences;
    if (!doc.text.empty()) {
        std::string current;
        current.reserve(doc.text.size());
        for (char c : doc.text) {
            current.push_back(c);
            if (c == '.' || c == '!' || c == '?') {
                if (!current.empty()) {
                    const auto tokens = wl2::tokenize(current);
                    if (!tokens.empty())
                        sentences.push_back(tokens);
                    current.clear();
                }
            }
        }
        if (!current.empty()) {
            const auto tokens = wl2::tokenize(current);
            if (!tokens.empty())
                sentences.push_back(tokens);
        }
    }
    if (!sentences.empty())
        return sentences;
    if (!doc.tokens.empty())
        return {doc.tokens};
    return {};
}

struct Token {
    enum Type { WORD, PHRASE, AND, OR, NOT, LEFT, RIGHT } type;
    std::string value;
};
std::vector<Token> lex(const std::string &query) {
    std::vector<Token> result;
    for (size_t i = 0; i < query.size();) {
        unsigned char c = query[i];
        if (std::isspace(c)) {
            ++i;
            continue;
        }
        if (c == '(') {
            result.push_back({Token::LEFT, "("});
            ++i;
            continue;
        }
        if (c == ')') {
            result.push_back({Token::RIGHT, ")"});
            ++i;
            continue;
        }
        if (c == '"') {
            const size_t start = ++i;
            while (i < query.size() && query[i] != '"')
                ++i;
            if (i == query.size())
                throw std::runtime_error("Unclosed quoted phrase.");
            result.push_back({Token::PHRASE, query.substr(start, i - start)});
            ++i;
            continue;
        }
        if (std::isalnum(c) || c == '_' || c == '*') {
            const size_t start = i++;
            while (i < query.size()) {
                const unsigned char next = query[i];
                if (!std::isalnum(next) && next != '_' && next != '*')
                    break;
                ++i;
            }
            const std::string raw_word = query.substr(start, i - start);
            if (raw_word == "AND")
                result.push_back({Token::AND, raw_word});
            else if (raw_word == "OR")
                result.push_back({Token::OR, raw_word});
            else if (raw_word == "NOT")
                result.push_back({Token::NOT, raw_word});
            else {
                const std::string word = normalize(raw_word);
                if (word.find('*') != std::string::npos || !wl2::is_stopword(word))
                    result.push_back({Token::WORD, word.find('*') == std::string::npos
                                                      ? wl2::lemmatize(word) : word});
            }
            continue;
        }
        ++i;
    }
    return result;
}

bool contains_only_stopwords(const std::string &query) {
    bool found_stopword = false;
    for (const auto &word : wl2::tokenize(query)) {
        if (word == "and" || word == "or" || word == "not")
            continue;
        if (!wl2::is_stopword(word))
            return false;
        found_stopword = true;
    }
    return found_stopword;
}

using IdSet = std::set<int>;
IdSet set_union_of(const IdSet &a, const IdSet &b) {
    IdSet result;
    std::set_union(a.begin(), a.end(), b.begin(), b.end(),
                   std::inserter(result, result.end()));
    return result;
}

IdSet set_difference_of(const IdSet &a, const IdSet &b) {
    IdSet result;
    std::set_difference(a.begin(), a.end(), b.begin(), b.end(),
                        std::inserter(result, result.end()));
    return result;
}

class QueryParser {
  public:
    explicit QueryParser(const std::vector<Token> &tokens) : tokens_(tokens) {}
    IdSet parse() {
        if (tokens_.empty())
            return {};
        IdSet result = parse_or();
        if (position_ != tokens_.size())
            throw std::runtime_error("Unexpected query operator or parenthesis.");
        return result;
    }

  private:
    const std::vector<Token> &tokens_;
    size_t position_ = 0;
    IdSet all_docs() const {
        IdSet result;
        if (docs)
            for (const auto &d : *docs)
                result.insert(d.docId);
        return result;
    }
    bool starts_unary() const {
        return position_ < tokens_.size() &&
               (tokens_[position_].type == Token::WORD ||
                tokens_[position_].type == Token::PHRASE || tokens_[position_].type == Token::NOT ||
                tokens_[position_].type == Token::LEFT);
    }
    IdSet parse_or() {
        IdSet result = parse_and();
        while (position_ < tokens_.size() && tokens_[position_].type == Token::OR) {
            ++position_;
            result = set_union_of(result, parse_and());
        }
        return result;
    }
    IdSet parse_and() {
        IdSet result = parse_unary();
        while (position_ < tokens_.size()) {
            if (tokens_[position_].type == Token::AND) {
                ++position_;
            } else if (!starts_unary()) {
                break;
            }

            const IdSet right = parse_unary();
            IdSet intersection;
            std::set_intersection(result.begin(), result.end(), right.begin(), right.end(),
                                  std::inserter(intersection, intersection.end()));
            result = std::move(intersection);
        }
        return result;
    }
    IdSet parse_unary() {
        if (position_ >= tokens_.size())
            throw std::runtime_error("Expected a query term after operator.");
        if (tokens_[position_].type == Token::NOT) {
            ++position_;
            IdSet result = all_docs();
            const IdSet excluded = parse_unary();
            return set_difference_of(result, excluded);
        }
        if (tokens_[position_].type == Token::LEFT) {
            ++position_;
            IdSet result = parse_or();
            if (position_ >= tokens_.size() || tokens_[position_].type != Token::RIGHT)
                throw std::runtime_error("Missing closing parenthesis.");
            ++position_;
            return result;
        }
        const Token token = tokens_[position_++];
        if (token.type == Token::WORD)
            return term_matches(token.value);
        if (token.type == Token::PHRASE)
            return phrase_matches(token.value);
        throw std::runtime_error("Expected a term or phrase.");
    }
    std::vector<std::string> expand(const std::string &pattern) const {
        auto result = trie_expansion(pattern);
        result.erase(std::remove_if(result.begin(), result.end(), [&](const auto &term) { return !df.count(term); }), result.end());
        std::sort(result.begin(), result.end());
        return result;
    }
    IdSet term_matches(const std::string &pattern) const {
        IdSet result;
        PostingList combined;
        for (const auto &term : expand(pattern)) {
            PostingList *posting = inverted_index ? inverted_index->get(term) : nullptr;
            if (posting) combined = PostingsOperations::union_(combined, *posting);
        }
        for (int id : PostingsOperations::extract_doc_ids(combined)) result.insert(id);
        return result;
    }
    IdSet phrase_matches(const std::string &phrase) const {
        const auto phrase_terms = wl2::tokenize(phrase);
        if (phrase_terms.empty() || !docs)
            return {};
        std::vector<std::vector<std::string>> alternatives;
        for (const auto &word : phrase_terms) {
            if (word.find('*') == std::string::npos)
                alternatives.push_back({normalize(word)});
            else {
                const auto matches = trie_expansion(word);
                if (matches.empty())
                    return {};
                alternatives.push_back(matches);
            }
        }
        IdSet result;
        for (const auto &doc : *docs) {
            const auto sentences = sentence_tokens_for_document(doc);
            for (const auto &sentence : sentences) {
                if (sentence.size() < phrase_terms.size())
                    continue;
                for (size_t start = 0; start + phrase_terms.size() <= sentence.size(); ++start) {
                    bool match = true;
                    for (size_t offset = 0; offset < phrase_terms.size() && match; ++offset) {
                        const std::string token = normalize(sentence[start + offset]);
                        const auto &allowed = alternatives[offset];
                        match = std::any_of(allowed.begin(), allowed.end(),
                                             [&](const std::string &candidate) {
                                                 return candidate == token ||
                                                        wildcard_matches(token, candidate);
                                             });
                    }
                    if (match) {
                        result.insert(doc.docId);
                        break;
                    }
                }
            }
        }
        return result;
    }
};
} // namespace

void initialize_query_processor(const std::vector<Document> *input) {
    docs = input;
    terms.clear();
    df.clear();
    inverted_index.reset();
    vocabulary_trie.reset();
    if (!docs) {
        version = "uninitialized";
        return;
    }
    inverted_index = std::make_unique<Inverted_Index>();
    inverted_index->build(*docs);
    vocabulary_trie = std::make_unique<Trie>();
    uint64_t hash = 14695981039346656037ULL;
    for (const auto &doc : *docs) {
        auto &counts = terms[doc.docId];
        hash ^= static_cast<uint64_t>(doc.docId);
        hash *= 1099511628211ULL;
        for (const auto &token : terms_for_document(doc)) {
            ++counts[token];
            if (trie_word(token)) {
                vocabulary_trie->insert(token);
                vocabulary_trie->insertReversed(token);
            }
            for (unsigned char c : token) {
                hash ^= c;
                hash *= 1099511628211ULL;
            }
        }
        for (const auto &token : document_tokens(doc)) {
            const auto trie_token = normalize(token);
            if (trie_word(trie_token)) {
                vocabulary_trie->insert(trie_token);
                vocabulary_trie->insertReversed(trie_token);
            }
        }
        for (const auto &term : counts)
            ++df[term.first];
    }
    version = "w2-" + std::to_string(docs->size()) + "-" + std::to_string(hash);
}
QueryResult resolve_query(const std::string &query) {
    QueryResult result;
    if (!docs)
        return result;
    std::vector<Token> tokens;
    IdSet matches;
    try {
        tokens = lex(query);
        QueryParser parser(tokens);
        matches = parser.parse();
    } catch (const std::exception &) {
        return result;
    }

    if (contains_only_stopwords(query)) {
        for (int id = 1; id <= 10; ++id)
            result.candidates.emplace(id, std::unordered_map<std::string, int>{});
        result.candidates.emplace(STOPWORDS_ONLY_SENTINEL_DOC_ID,
                                  std::unordered_map<std::string, int>{});
        return result;
    }

    std::set<std::string> query_terms;
    for (const auto &token : tokens) {
        if (token.type == Token::WORD)
            query_terms.insert(token.value);
        else if (token.type == Token::PHRASE)
            for (const auto &word : split_words(token.value))
                query_terms.insert(word);
    }
    std::set<std::string> expanded_terms;
    for (const auto &word : query_terms) {
        for (const auto &term : trie_expansion(word))
            expanded_terms.insert(term);
        if (word.find('*') == std::string::npos && df.count(word))
            expanded_terms.insert(word);
    }
    for (const auto &word : expanded_terms)
        result.doc_freq[word] = df[word];
    for (int id : matches) {
        auto &frequencies = result.candidates[id];
        const auto found = terms.find(id);
        if (found == terms.end())
            continue;
        for (const auto &word : expanded_terms) {
            auto count = found->second.find(word);
            if (count != found->second.end())
                frequencies[word] = count->second;
        }
    }
    return result;
}
CorpusStats get_corpus_stats() {
    size_t total = 0;
    if (docs)
        for (const auto &doc : *docs)
            total += terms_for_document(doc).size();
    return {docs ? static_cast<int>(docs->size()) : 0,
            docs && !docs->empty() ? static_cast<double>(total) / docs->size() : 0.0};
}
std::string get_index_version() {
    return version;
}
std::unordered_map<int, DocSnippetData> get_doc_snippet_data(const std::vector<int> &ids) {
    std::unordered_map<int, DocSnippetData> result;
    if (!docs)
        return result;
    for (int id : ids) {
        const Document *doc = find_document(id);
        if (doc)
            result[id] = {doc->title, doc->url, document_text(*doc)};
    }
    return result;
}
std::unordered_map<int, std::unordered_map<std::string, int>>
get_doc_terms(const std::vector<int> &ids) {
    std::unordered_map<int, std::unordered_map<std::string, int>> result;
    if (!docs)
        return result;
    for (int id : ids) {
        const Document *doc = find_document(id);
        if (!doc)
            continue;
        auto &counts = result[id];
        for (const auto &token : terms_for_document(*doc))
            ++counts[token];
    }
    return result;
}
