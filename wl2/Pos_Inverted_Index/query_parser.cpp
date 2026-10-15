
#include "query_parser.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <iterator>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace
{
    constexpr const char* BOUNDARY_TOKEN = "__section_boundary__";
    const vector<Document>* g_documents = nullptr;
    Trie* g_prefix_trie = nullptr;
    Trie* g_reversed_suffix_trie = nullptr;

    unordered_map<int, const Document*> g_docs_by_id;
    unordered_map<int, unordered_map<string, int>> g_term_counts;
    unordered_map<string, int> g_doc_frequency;
    unordered_set<string> g_vocabulary;

    int g_total_docs = 0;
    double g_average_length = 0.0;
    string g_version = "uninitialized";

    string normalize(string word)
    {
        for (char& c : word)
            c = static_cast<char>(
                tolower(static_cast<unsigned char>(c)));

        return word;
    }

    bool is_word_char(char c)
    {
        return isalnum(static_cast<unsigned char>(c)) || c == '_';
    }

    vector<string> split_words(const string& text)
    {
        vector<string> words;
        string current;

        for (char c : text)
        {
            if (is_word_char(c))
            {
                current += static_cast<char>(
                    tolower(static_cast<unsigned char>(c)));
            }
            else if (!current.empty())
            {
                words.push_back(current);
                current.clear();
            }
        }

        if (!current.empty())
            words.push_back(current);

        return words;
    }

    struct Token
    {
        enum Type
        {
            WORD, PHRASE, AND_OP, OR_OP,
            NOT_OP, LPAREN, RPAREN
        };

        Type type;
        string value;
    };

    vector<Token> tokenize_query(const string& query)
    {
        vector<Token> result;
        size_t i = 0;

        while (i < query.size())
        {
            if (isspace(static_cast<unsigned char>(query[i])))
            {
                ++i;
                continue;
            }

            if (query[i] == '(')
            {
                result.push_back({Token::LPAREN, "("});
                ++i;
                continue;
            }

            if (query[i] == ')')
            {
                result.push_back({Token::RPAREN, ")"});
                ++i;
                continue;
            }

            if (query[i] == '"')
            {
                ++i;
                string phrase;

                while (i < query.size() && query[i] != '"')
                    phrase += query[i++];

                if (i == query.size())
                    throw runtime_error("Unclosed phrase quotation.");

                ++i;
                result.push_back(
                    {Token::PHRASE, normalize(phrase)});
                continue;
            }

            if (is_word_char(query[i]) || query[i] == '*')
            {
                string word;

                while (i < query.size() &&
                       (is_word_char(query[i]) || query[i] == '*'))
                {
                    word += query[i++];
                }

                word = normalize(word);

                if (word == "and")
                    result.push_back({Token::AND_OP, word});
                else if (word == "or")
                    result.push_back({Token::OR_OP, word});
                else if (word == "not")
                    result.push_back({Token::NOT_OP, word});
                else
                    result.push_back({Token::WORD, word});

                continue;
            }

            ++i;
        }

        return result;
    }

    vector<string> expand_term(const string& pattern)
    {
        if (pattern.find('*') == string::npos)
        {
            if (g_vocabulary.count(pattern))
                return {pattern};

            return {};
        }

        size_t star = pattern.find('*');

        if (pattern.find('*', star + 1) != string::npos)
            return {};

        string prefix = pattern.substr(0, star);
        string suffix = pattern.substr(star + 1);

        vector<string> matches;

        for (const string& word : g_vocabulary)
        {
            bool prefix_matches =
                prefix.empty() ||
                word.compare(0, prefix.size(), prefix) == 0;

            bool suffix_matches =
                suffix.empty() ||
                (word.size() >= suffix.size() &&
                 word.compare(word.size() - suffix.size(),
                              suffix.size(), suffix) == 0);

            if (prefix_matches && suffix_matches)
                matches.push_back(word);
        }

        sort(matches.begin(), matches.end());
        return matches;
    }

    set<int> all_document_ids()
    {
        set<int> result;

        for (const auto& entry : g_docs_by_id)
            result.insert(entry.first);

        return result;
    }

    set<int> documents_for_term(const string& term)
    {
        set<int> result;

        for (const auto& entry : g_term_counts)
        {
            if (entry.second.count(term))
                result.insert(entry.first);
        }

        return result;
    }

    set<int> union_of(const set<int>& a, const set<int>& b)
    {
        set<int> result = a;
        result.insert(b.begin(), b.end());
        return result;
    }

    set<int> intersection_of(const set<int>& a, const set<int>& b)
    {
        set<int> result;

        set_intersection(
            a.begin(), a.end(),
            b.begin(), b.end(),
            inserter(result, result.begin()));

        return result;
    }

    set<int> documents_for_phrase(const string& phrase)
    {
        vector<string> terms = split_words(phrase);

        if (terms.empty())
            return {};

        set<int> result;

        for (const auto& entry : g_docs_by_id)
        {
            const vector<string>& tokens = entry.second->tokens;

            if (tokens.size() < terms.size())
                continue;

            for (size_t i = 0; i + terms.size() <= tokens.size(); ++i)
            {
                bool matched = true;

                for (size_t j = 0; j < terms.size(); ++j)
                {
                    if (tokens[i + j] == BOUNDARY_TOKEN || normalize(tokens[i + j]) != terms[j])
                    {
                        matched = false;
                        break;
                    }
                }

                if (matched)
                {
                    result.insert(entry.first);
                    break;
                }
            }
        }

        return result;
    }

    struct Parser
    {
        const vector<Token>& tokens;
        size_t pos = 0;

        explicit Parser(const vector<Token>& input)
            : tokens(input) {}

        bool accept(Token::Type type)
        {
            if (pos < tokens.size() && tokens[pos].type == type)
            {
                ++pos;
                return true;
            }

            return false;
        }

        set<int> parse_or()
        {
            set<int> result = parse_and();

            while (accept(Token::OR_OP))
                result = union_of(result, parse_and());

            return result;
        }

        set<int> parse_and()
        {
            set<int> result = parse_unary();

            while (pos < tokens.size() &&
                   tokens[pos].type != Token::OR_OP &&
                   tokens[pos].type != Token::RPAREN)
            {
                if (accept(Token::AND_OP))
                {
                    result = intersection_of(result, parse_unary());
                }
                else if (tokens[pos].type == Token::WORD ||
                         tokens[pos].type == Token::PHRASE ||
                         tokens[pos].type == Token::NOT_OP ||
                         tokens[pos].type == Token::LPAREN)
                {
                    result = intersection_of(result, parse_unary());
                }
                else
                {
                    break;
                }
            }

            return result;
        }

        set<int> parse_unary()
        {
            if (accept(Token::NOT_OP))
            {
                set<int> result = all_document_ids();
                set<int> excluded = parse_unary();

                for (int id : excluded)
                    result.erase(id);

                return result;
            }

            if (accept(Token::LPAREN))
            {
                set<int> result = parse_or();

                if (!accept(Token::RPAREN))
                    throw runtime_error("Missing closing parenthesis.");

                return result;
            }

            if (pos >= tokens.size())
                throw runtime_error("Expected a search term.");

            Token token = tokens[pos++];

            if (token.type == Token::PHRASE)
                return documents_for_phrase(token.value);

            if (token.type != Token::WORD)
                throw runtime_error("Invalid query syntax.");

            set<int> result;

            for (const string& term : expand_term(token.value))
                result = union_of(result, documents_for_term(term));

            return result;
        }
    };

    void rebuild_document_data()
    {
        g_docs_by_id.clear();
        g_term_counts.clear();
        g_doc_frequency.clear();
        g_vocabulary.clear();

        g_total_docs = 0;
        g_average_length = 0.0;

        if (!g_documents)
            return;

        size_t total_tokens = 0;

for (const Document& doc : *g_documents)
{
    g_docs_by_id[doc.docId] = &doc;
    auto& counts = g_term_counts[doc.docId];

    for (const string& raw : doc.tokens)
    {
        if (raw == BOUNDARY_TOKEN)
            continue;

        string term = normalize(raw);

        if (term.empty())
            continue;

        ++counts[term];
        g_vocabulary.insert(term);
        ++total_tokens;
    }
}

        g_total_docs = static_cast<int>(g_docs_by_id.size());

        for (const auto& doc : g_term_counts)
        {
            for (const auto& term : doc.second)
                ++g_doc_frequency[term.first];
        }

        if (g_total_docs > 0)
        {
            g_average_length =
                static_cast<double>(total_tokens) / g_total_docs;
        }

        uint64_t hash = 14695981039346656037ULL;

        for (const Document& doc : *g_documents)
        {
            hash ^= static_cast<uint64_t>(doc.docId);
            hash *= 1099511628211ULL;

            for (const string& token : doc.tokens)
            {
                for (unsigned char c : token)
                {
                    hash ^= c;
                    hash *= 1099511628211ULL;
                }

                hash ^= 255;
                hash *= 1099511628211ULL;
            }
        }

        ostringstream version;
        version << "w2-index-v1-" << g_total_docs << "-" << hash;
        g_version = version.str();
    }
}

// Call this after Worklet 2 has loaded the documents.
void initialize_query_processor(
    HashMap* index,
    const vector<Document>* documents,
    Trie* prefix_trie,
    Trie* reversed_suffix_trie)
{
    // Search using document tokens, without accessing private posting-list data.
    (void)index;

    g_documents = documents;
    g_prefix_trie = prefix_trie;
    g_reversed_suffix_trie = reversed_suffix_trie;

    rebuild_document_data();
}

QueryResult resolve_query(const string& query_string)
{
    if (!g_documents)
        throw runtime_error(
            "Initialize the query processor before searching.");

    QueryResult output;
    vector<Token> tokens = tokenize_query(query_string);

    if (tokens.empty())
        return output;

    Parser parser(tokens);
    set<int> matches = parser.parse_or();

    if (parser.pos != tokens.size())
        throw runtime_error("Unexpected token in query.");

    set<string> query_terms;

    for (const Token& token : tokens)
    {
        if (token.type == Token::WORD)
        {
            vector<string> expanded = expand_term(token.value);
            query_terms.insert(expanded.begin(), expanded.end());
        }
        else if (token.type == Token::PHRASE)
        {
            vector<string> terms = split_words(token.value);
            query_terms.insert(terms.begin(), terms.end());
        }
    }

    for (const string& term : query_terms)
    {
        auto it = g_doc_frequency.find(term);

        output.doc_freq[term] =
            (it == g_doc_frequency.end()) ? 0 : it->second;
    }

    for (int doc_id : matches)
    {
        auto doc = g_term_counts.find(doc_id);

        if (doc == g_term_counts.end())
            continue;

        auto& counts = output.candidates[doc_id];

        for (const string& term : query_terms)
        {
            auto it = doc->second.find(term);

            if (it != doc->second.end())
                counts[term] = it->second;
        }
    }

    return output;
}

CorpusStats get_corpus_stats()
{
    return {g_total_docs, g_average_length};
}

string get_index_version()
{
    return g_version;
}

unordered_map<int, DocSnippetData>
get_doc_snippet_data(const vector<int>& doc_ids)
{
    unordered_map<int, DocSnippetData> result;

    for (int id : doc_ids)
    {
        auto it = g_docs_by_id.find(id);

        if (it == g_docs_by_id.end())
            continue;

        DocSnippetData data;

        // The current Document structure does not store the original URL or title.
        data.title = "";
        data.url = "";

        for (size_t i = 0; i < it->second->tokens.size(); ++i)
        {
            if (i > 0)
                data.text += " ";

            data.text += it->second->tokens[i];
        }

        result[id] = data;
    }

    return result;
}

unordered_map<int, unordered_map<string, int>>
get_doc_terms(const vector<int>& doc_ids)
{
    unordered_map<int, unordered_map<string, int>> result;

    for (int id : doc_ids)
    {
        auto it = g_term_counts.find(id);

        if (it != g_term_counts.end())
            result[id] = it->second;
    }

    return result;
}
