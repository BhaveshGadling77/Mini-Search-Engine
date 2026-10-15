#include "query_parser.h"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <set>
#include <stdexcept>

namespace {
const std::vector<Document> *docs = nullptr;
std::unordered_map<int, std::unordered_map<std::string, int>> terms;
std::unordered_map<std::string, int> df;
std::string version = "uninitialized";

std::string normalize(std::string value) {
    for (char &c : value)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return value;
}
std::vector<std::string> split_words(const std::string &input) {
    std::vector<std::string> result;
    std::string current;
    for (unsigned char c : input) {
        if (std::isalnum(c) || c == '_' || c == '*')
            current += static_cast<char>(std::tolower(c));
        else if (!current.empty()) {
            result.push_back(current);
            current.clear();
        }
    }
    if (!current.empty())
        result.push_back(current);
    return result;
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
            std::string word = normalize(query.substr(start, i - start));
            if (word == "and")
                result.push_back({Token::AND, word});
            else if (word == "or")
                result.push_back({Token::OR, word});
            else if (word == "not")
                result.push_back({Token::NOT, word});
            else
                result.push_back({Token::WORD, word});
            continue;
        }
        ++i;
    }
    return result;
}
using IdSet = std::set<int>;
IdSet set_union_of(const IdSet &a, const IdSet &b) {
    IdSet r = a;
    r.insert(b.begin(), b.end());
    return r;
}
IdSet set_intersection_of(const IdSet &a, const IdSet &b) {
    IdSet r;
    std::set_intersection(a.begin(), a.end(), b.begin(), b.end(), std::inserter(r, r.begin()));
    return r;
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
                result = set_intersection_of(result, parse_unary());
            } else if (starts_unary())
                result = set_intersection_of(result, parse_unary());
            else
                break;
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
            for (int id : excluded)
                result.erase(id);
            return result;
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
        if (pattern.find('*') == std::string::npos)
            return df.count(pattern) ? std::vector<std::string>{pattern}
                                     : std::vector<std::string>{};
        if (pattern.find('*', pattern.find('*') + 1) != std::string::npos)
            return {};
        const size_t star = pattern.find('*');
        const std::string prefix = pattern.substr(0, star), suffix = pattern.substr(star + 1);
        std::vector<std::string> result;
        for (const auto &entry : df) {
            const auto &term = entry.first;
            if (term.size() >= prefix.size() + suffix.size() &&
                term.compare(0, prefix.size(), prefix) == 0 &&
                term.compare(term.size() - suffix.size(), suffix.size(), suffix) == 0)
                result.push_back(term);
        }
        std::sort(result.begin(), result.end());
        return result;
    }
    IdSet term_matches(const std::string &pattern) const {
        IdSet result;
        for (const auto &term : expand(pattern))
            for (const auto &doc : terms)
                if (doc.second.count(term))
                    result.insert(doc.first);
        return result;
    }
    IdSet phrase_matches(const std::string &phrase) const {
        const auto phrase_terms = split_words(phrase);
        if (phrase_terms.empty() || !docs)
            return {};
        std::vector<std::vector<std::string>> alternatives;
        for (const auto &word : phrase_terms) {
            if (word.find('*') == std::string::npos)
                alternatives.push_back({word});
            else
                alternatives.push_back(expand(word));
        }
        if (std::any_of(alternatives.begin(), alternatives.end(),
                        [](const auto &a) { return a.empty(); }))
            return {};
        IdSet result;
        for (const auto &doc : *docs) {
            // Document::tokens has stop words removed by Worklet 1, so it cannot
            // preserve exact phrase positions. Prefer the original page text.
            // Hand-built/test documents may only provide tokens, so retain that
            // as a fallback.
            const auto document_terms = split_words(doc.text.empty() ? [&doc]() {
                std::string joined;
                for (const auto &token : doc.tokens) {
                    if (!joined.empty()) joined += ' ';
                    joined += token;
                }
                return joined;
            }() : doc.text);
            if (document_terms.size() < phrase_terms.size())
                continue;
            for (size_t start = 0; start + phrase_terms.size() <= document_terms.size(); ++start) {
                bool match = true;
                for (size_t offset = 0; offset < phrase_terms.size() && match; ++offset) {
                    const std::string &token = document_terms[start + offset];
                    match = std::find(alternatives[offset].begin(), alternatives[offset].end(),
                                      token) != alternatives[offset].end();
                }
                if (match) {
                    result.insert(doc.docId);
                    break;
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
    if (!docs) {
        version = "uninitialized";
        return;
    }
    uint64_t hash = 14695981039346656037ULL;
    for (const auto &doc : *docs) {
        auto &counts = terms[doc.docId];
        hash ^= static_cast<uint64_t>(doc.docId);
        hash *= 1099511628211ULL;
        for (const auto &raw : doc.tokens) {
            const auto token = normalize(raw);
            ++counts[token];
            for (unsigned char c : token) {
                hash ^= c;
                hash *= 1099511628211ULL;
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
    const auto tokens = lex(query);
    QueryParser parser(tokens);
    const IdSet matches = parser.parse();
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
        if (word.find('*') == std::string::npos)
            expanded_terms.insert(word);
        else {
            const size_t star = word.find('*');
            const std::string prefix = word.substr(0, star), suffix = word.substr(star + 1);
            for (const auto &entry : df)
                if (entry.first.size() >= prefix.size() + suffix.size() &&
                    entry.first.compare(0, prefix.size(), prefix) == 0 &&
                    entry.first.compare(entry.first.size() - suffix.size(), suffix.size(),
                                        suffix) == 0)
                    expanded_terms.insert(entry.first);
        }
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
            total += doc.tokens.size();
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
    for (int id : ids)
        for (const auto &doc : *docs)
            if (doc.docId == id) {
                DocSnippetData data{doc.title, doc.url, doc.text};
                if (data.text.empty())
                    for (const auto &token : doc.tokens) {
                        if (!data.text.empty())
                            data.text += ' ';
                        data.text += token;
                    }
                result[id] = data;
                break;
            }
    return result;
}
std::unordered_map<int, std::unordered_map<std::string, int>>
get_doc_terms(const std::vector<int> &ids) {
    std::unordered_map<int, std::unordered_map<std::string, int>> result;
    if (!docs)
        return result;
    for (int id : ids)
        for (const auto &doc : *docs)
            if (doc.docId == id) {
                auto &counts = result[id];
                for (const auto &token : doc.tokens)
                    ++counts[normalize(token)];
                break;
            }
    return result;
}
