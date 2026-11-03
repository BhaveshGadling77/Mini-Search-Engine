#include "query_parser.h"
#include "../Inverted_Index/Inverted_Index.h"
#include "../boolean_operations/PostingsOperations.h"
#include "../trie/trie.h"
#include "../lib/src/include/text_processing.h"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <limits>
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

class QueryParser {
  public:
    explicit QueryParser(const std::vector<Token> &tokens) : tokens_(tokens) {}
    PostingList parse() {
        if (tokens_.empty())
            return {};
        PostingList result = parse_or();
        if (position_ != tokens_.size())
            throw std::runtime_error("Unexpected query operator or parenthesis.");
        return result;
    }

  private:
    const std::vector<Token> &tokens_;
    size_t position_ = 0;
    // Build the complete document universe from the inverted index as a sorted
    // PostingList so that NOT can subtract from it via difference().
    PostingList all_docs() const {
        PostingList universe;
        if (docs) {
            // Collect every docId that appears anywhere in the inverted index.
            // Since we also need positions/frequency for downstream scoring,
            // we merge all posting lists into one universe list.
            std::set<int> seen;
            for (const auto &d : *docs)
                seen.insert(d.docId);
            for (int id : seen)
                universe.appendSortedPosting({id, {}, 0});
        }
        return universe;
    }
    bool starts_unary() const {
        return position_ < tokens_.size() &&
               (tokens_[position_].type == Token::WORD ||
                tokens_[position_].type == Token::PHRASE || tokens_[position_].type == Token::NOT ||
                tokens_[position_].type == Token::LEFT);
    }
    PostingList parse_or() {
        PostingList result = parse_and();
        while (position_ < tokens_.size() && tokens_[position_].type == Token::OR) {
            ++position_;
            result = PostingsOperations::union_(result, parse_and());
        }
        return result;
    }
    PostingList parse_and() {
        PostingList result = parse_unary();
        while (position_ < tokens_.size()) {
            if (tokens_[position_].type == Token::AND) {
                ++position_;
            } else if (!starts_unary()) {
                break;
            }

            result = PostingsOperations::intersect(result, parse_unary());
        }
        return result;
    }
    PostingList parse_unary() {
        if (position_ >= tokens_.size())
            throw std::runtime_error("Expected a query term after operator.");
        if (tokens_[position_].type == Token::NOT) {
            ++position_;
            PostingList universe = all_docs();
            PostingList excluded = parse_unary();
            return PostingsOperations::difference(universe, excluded);
        }
        if (tokens_[position_].type == Token::LEFT) {
            ++position_;
            PostingList result = parse_or();
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
    // Merge expanded-term posting lists using union_with_skips.
    PostingList term_matches(const std::string &pattern) const {
        PostingList combined;
        for (const auto &term : expand(pattern)) {
            PostingList *posting = inverted_index ? inverted_index->get(term) : nullptr;
            if (posting) combined = PostingsOperations::union_with_skips(combined, *posting);
        }
        return combined;
    }
    PostingList phrase_matches(const std::string &phrase) const {
        const auto phrase_terms = wl2::tokenize(phrase);
        if (phrase_terms.empty() || !inverted_index)
            return {};

        std::vector<std::vector<std::string>> alternatives;
        for (const auto &word : phrase_terms) {
            if (word.find('*') == std::string::npos)
                alternatives.push_back({wl2::is_stopword(word) ? word : wl2::lemmatize(word)});
            else {
                const auto matches = trie_expansion(word);
                if (matches.empty())
                    return {};
                auto unique_matches = matches;
                std::sort(unique_matches.begin(), unique_matches.end());
                unique_matches.erase(std::unique(unique_matches.begin(), unique_matches.end()),
                                     unique_matches.end());
                alternatives.push_back(std::move(unique_matches));
            }
        }

        std::vector<std::vector<const PostingList *>> positional_lists;
        positional_lists.reserve(alternatives.size());
        for (const auto &allowed_terms : alternatives) {
            std::vector<const PostingList *> lists;
            for (const auto &term : allowed_terms) {
                PostingList *posting = inverted_index->get_positional(term);
                if (posting && !posting->get_all().empty())
                    lists.push_back(posting);
            }
            if (lists.empty())
                return {};
            positional_lists.push_back(std::move(lists));
        }

        // Start from the least frequent phrase slot to minimize candidate
        // documents. The postings are sorted by docId by the inverted index.
        size_t seed_slot = 0;
        size_t seed_frequency = std::numeric_limits<size_t>::max();
        for (size_t slot = 0; slot < positional_lists.size(); ++slot) {
            size_t frequency = 0;
            for (const PostingList *list : positional_lists[slot])
                frequency += list->get_all().size();
            if (frequency < seed_frequency) {
                seed_frequency = frequency;
                seed_slot = slot;
            }
        }

        std::vector<int> candidate_ids;
        for (const PostingList *list : positional_lists[seed_slot])
            for (const Posting &posting : list->get_all())
                candidate_ids.push_back(posting.docId);
        std::sort(candidate_ids.begin(), candidate_ids.end());
        candidate_ids.erase(std::unique(candidate_ids.begin(), candidate_ids.end()),
                            candidate_ids.end());

        PostingList result;
        result.reserve(candidate_ids.size());
        for (int doc_id : candidate_ids) {
            std::vector<std::vector<const Posting *>> document_postings(positional_lists.size());
            for (size_t slot = 0; slot < positional_lists.size(); ++slot) {
                for (const PostingList *list : positional_lists[slot]) {
                    const auto &postings = list->get_all();
                    const auto found = std::lower_bound(
                        postings.begin(), postings.end(), doc_id,
                        [](const Posting &posting, int id) { return posting.docId < id; });
                    if (found != postings.end() && found->docId == doc_id)
                        document_postings[slot].push_back(&*found);
                }
            }

            bool matched = false;
            for (const PostingList *seed_list : positional_lists[seed_slot]) {
                const auto &postings = seed_list->get_all();
                const auto found = std::lower_bound(
                    postings.begin(), postings.end(), doc_id,
                    [](const Posting &posting, int id) { return posting.docId < id; });
                if (found == postings.end() || found->docId != doc_id)
                    continue;

                for (int seed_position : found->positions) {
                    if (seed_position < static_cast<int>(seed_slot))
                        continue;
                    const int phrase_start = seed_position - static_cast<int>(seed_slot);
                    bool full_match = true;
                    for (size_t slot = 0; slot < document_postings.size() && full_match; ++slot) {
                        const int expected_position = phrase_start + static_cast<int>(slot);
                        const bool slot_matches = std::any_of(
                            document_postings[slot].begin(), document_postings[slot].end(),
                            [expected_position](const Posting *posting) {
                                return std::binary_search(posting->positions.begin(),
                                                          posting->positions.end(),
                                                          expected_position);
                            });
                        full_match = slot_matches;
                    }
                    if (full_match) {
                        matched = true;
                        break;
                    }
                }
                if (matched)
                    break;
            }

            if (matched)
                result.appendSortedPosting({doc_id, {}, 0});
        }
        return result;
    }
};
} // namespace

std::vector<std::string> expand_wildcard_terms(const std::string &pattern) {
    if (pattern.empty())
        return {};
    auto matches = trie_expansion(pattern);
    if (matches.empty() && pattern.find('*') == std::string::npos && df.count(pattern))
        return std::vector<std::string>{pattern};
    return matches;
}

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
        // Phrase postings retain stopwords and sentence boundaries, so include
        // the source text in the index version used by query-result caches.
        if (!doc.text.empty()) {
            for (unsigned char c : doc.text) {
                hash ^= c;
                hash *= 1099511628211ULL;
            }
        } else {
            for (const auto &token : doc.tokens) {
                for (unsigned char c : token) {
                    hash ^= c;
                    hash *= 1099511628211ULL;
                }
                hash ^= 0xff;
                hash *= 1099511628211ULL;
            }
        }
        hash ^= 0xfe;
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
    PostingList matches;
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
    for (int id : PostingsOperations::extract_doc_ids(matches)) {
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
