#include "CorpusReader.h"
#include <cctype>
#include <fstream>
#include <iostream>
#include <sstream>

static int extractDocId(const string &text, size_t objStart, size_t objEnd) {
    size_t keyPos = text.find("\"doc_id\"", objStart);
    if (keyPos == string::npos || keyPos > objEnd)
        return -1;

    size_t colonPos = text.find(':', keyPos);
    if (colonPos == string::npos || colonPos > objEnd)
        return -1;

    size_t i = colonPos + 1;

    // Skip spaces and other whitespace
    while (i < objEnd && isspace(static_cast<unsigned char>(text[i]))) {
        i++;
    }

    // Skip opening quote if doc_id is stored as a string
    if (i < objEnd && text[i] == '"') {
        i++;
    }

    size_t start = i;

    // Read the numeric document ID
    if (i < objEnd && text[i] == '-') {
        i++;
    }

    while (i < objEnd && isdigit(static_cast<unsigned char>(text[i]))) {
        i++;
    }

    if (start == i || (i == start + 1 && text[start] == '-')) {
        return -1;
    }

    return stoi(text.substr(start, i - start));
}

static void skipWhitespace(const string &text, size_t &i, size_t end) {
    while (i < end && isspace(static_cast<unsigned char>(text[i])))
        ++i;
}

static string parseJsonString(const string &text, size_t &i, size_t end) {
    string value;
    if (i >= end || text[i] != '"')
        return value;
    ++i;
    while (i < end && text[i] != '"') {
        char c = text[i++];
        if (c == '\\' && i < end) {
            char escaped = text[i++];
            switch (escaped) {
            case '"':
                value += '"';
                break;
            case '\\':
                value += '\\';
                break;
            case '/':
                value += '/';
                break;
            case 'b':
                value += '\b';
                break;
            case 'f':
                value += '\f';
                break;
            case 'n':
                value += '\n';
                break;
            case 'r':
                value += '\r';
                break;
            case 't':
                value += '\t';
                break;
            default:
                value += escaped;
                break; // Preserve unsupported escapes safely.
            }
        } else {
            value += c;
        }
    }
    if (i < end)
        ++i;
    return value;
}

static size_t findTopLevelValue(const string &text, const string &wanted, size_t end) {
    size_t i = 0;
    skipWhitespace(text, i, end);
    if (i >= end || text[i++] != '{')
        return string::npos;
    while (i < end) {
        skipWhitespace(text, i, end);
        if (i >= end || text[i] == '}')
            break;
        if (text[i] != '"')
            return string::npos;
        string key = parseJsonString(text, i, end);
        skipWhitespace(text, i, end);
        if (i >= end || text[i++] != ':')
            return string::npos;
        skipWhitespace(text, i, end);
        const size_t valueStart = i;
        if (key == wanted)
            return valueStart;

        if (i < end && text[i] == '"') {
            (void)parseJsonString(text, i, end);
        } else if (i < end && (text[i] == '{' || text[i] == '[')) {
            const char open = text[i++];
            const char close = open == '{' ? '}' : ']';
            int depth = 1;
            bool inString = false, escaped = false;
            while (i < end && depth > 0) {
                const char c = text[i++];
                if (inString) {
                    if (escaped)
                        escaped = false;
                    else if (c == '\\')
                        escaped = true;
                    else if (c == '"')
                        inString = false;
                } else if (c == '"')
                    inString = true;
                else if (c == open)
                    ++depth;
                else if (c == close)
                    --depth;
            }
        } else {
            while (i < end && text[i] != ',' && text[i] != '}')
                ++i;
        }
        skipWhitespace(text, i, end);
        if (i < end && text[i] == ',')
            ++i;
        else
            break;
    }
    return string::npos;
}

static string extractString(const string &text, size_t start, size_t end, const string &key) {
    (void)start;
    size_t value = findTopLevelValue(text, key, end);
    if (value == string::npos || text[value] != '"')
        return "";
    return parseJsonString(text, value, end);
}

static vector<string> extractTokens(const string &text, size_t objStart, size_t objEnd) {
    (void)objStart;
    vector<string> tokens;
    size_t i = findTopLevelValue(text, "tokens", objEnd);
    if (i == string::npos || text[i] != '[')
        return tokens;
    ++i;
    while (i < objEnd) {
        skipWhitespace(text, i, objEnd);
        if (i >= objEnd || text[i] == ']')
            break;
        if (text[i] == '"')
            tokens.push_back(parseJsonString(text, i, objEnd));
        else
            while (i < objEnd && text[i] != ',' && text[i] != ']')
                ++i;
        skipWhitespace(text, i, objEnd);
        if (i < objEnd && text[i] == ',')
            ++i;
        else
            break;
    }
    return tokens;
}

vector<Document> readDocuments(const string &filename) {
    vector<Document> docs;
    ifstream file(filename);
    if (!file) {
        cerr << "Could not read file: " << filename << endl;
        return docs;
    }

    // The corpus is JSON Lines: each physical line is one complete document.
    // Parsing line-by-line avoids treating braces inside page text as JSON syntax.
    string line;
    while (getline(file, line)) {
        if (line.empty())
            continue;
        Document doc;
        doc.docId = extractDocId(line, 0, line.size());
        if (doc.docId == -1)
            continue;
        doc.title = extractString(line, 0, line.size(), "title");
        doc.url = extractString(line, 0, line.size(), "url");
        doc.text = extractString(line, 0, line.size(), "text");
        doc.tokens = extractTokens(line, 0, line.size());
        if (doc.tokens.empty() && !doc.text.empty()) {
            istringstream words(doc.text);
            string word;
            while (words >> word)
                doc.tokens.push_back(word);
        }
        docs.push_back(std::move(doc));
    }

    return docs;
}
