#include "CorpusReader.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cctype>

static string extractString(const string& text, size_t objStart,
                            size_t objEnd, const string& key) {
    size_t keyPos = text.find("\"" + key + "\"", objStart);
    if (keyPos == string::npos || keyPos > objEnd) return "";

    size_t colonPos = text.find(':', keyPos);
    if (colonPos == string::npos || colonPos > objEnd) return "";

    size_t start = text.find('"', colonPos + 1);
    if (start == string::npos || start > objEnd) return "";
    start++;

    size_t end = text.find('"', start);
    if (end == string::npos || end > objEnd) return "";

    return text.substr(start, end - start);
}

// ADDED: Extract a metadata value from the meta object
static string extractMetaValue(const string& text, size_t objStart,
                               size_t objEnd, const string& key) {
    size_t metaPos = text.find("\"meta\"", objStart);
    if (metaPos == string::npos || metaPos > objEnd) return "";

    size_t metaStart = text.find('{', metaPos);
    if (metaStart == string::npos || metaStart > objEnd) return "";

    size_t metaEnd = text.find('}', metaStart);
    if (metaEnd == string::npos || metaEnd > objEnd) return "";

    return extractString(text, metaStart, metaEnd, key);
}


static int extractMetaInt(const string& text, size_t objStart,
                          size_t objEnd, const string& key) {
    size_t metaPos = text.find("\"meta\"", objStart);
    if (metaPos == string::npos || metaPos > objEnd) return 0;

    size_t metaStart = text.find('{', metaPos);
    if (metaStart == string::npos || metaStart > objEnd) return 0;

    size_t metaEnd = text.find('}', metaStart);
    if (metaEnd == string::npos || metaEnd > objEnd) return 0;

    size_t keyPos = text.find("\"" + key + "\"", metaStart);
    if (keyPos == string::npos || keyPos > metaEnd) return 0;

    size_t colonPos = text.find(':', keyPos);
    if (colonPos == string::npos || colonPos > metaEnd) return 0;

    size_t start = colonPos + 1;

    while (start < metaEnd &&
           isspace(static_cast<unsigned char>(text[start]))) {
        start++;
    }

    // ADDED: Handle integer values stored as strings using stoi()
    if (start < metaEnd && text[start] == '"') {
        start++;
    }

    size_t end = start;

    if (end < metaEnd && text[end] == '-') {
        end++;
    }

    while (end < metaEnd &&
           isdigit(static_cast<unsigned char>(text[end]))) {
        end++;
    }

    if (start == end || (end == start + 1 && text[start] == '-')) {
        return 0;
    }

    try {
        return stoi(text.substr(start, end - start));
    } catch (...) {
        return 0;
    }
}

static string readWholeFile(const string& filename) {
    ifstream file(filename);
    stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

static int extractDocId(const string& text, size_t objStart, size_t objEnd) {
    size_t keyPos = text.find("\"doc_id\"", objStart);
    if (keyPos == string::npos || keyPos > objEnd) return -1;

    size_t colonPos = text.find(':', keyPos);
    if (colonPos == string::npos || colonPos > objEnd) return -1;

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

static vector<string> extractTokens(const string& text, size_t objStart, size_t objEnd) {
    vector<string> tokens;

    size_t keyPos = text.find("\"tokens\"", objStart);
    if (keyPos == string::npos || keyPos > objEnd) return tokens;

    size_t arrStart = text.find('[', keyPos);
    size_t arrEnd = text.find(']', arrStart);

    size_t i = arrStart + 1;
    while (i < arrEnd) {
        while (i < arrEnd && text[i] != '"') i++;
        if (i >= arrEnd) break;
        i++;

        string word;
        while (i < arrEnd && text[i] != '"') {
            word += text[i];
            i++;
        }
        i++;

        tokens.push_back(word);
    }

    return tokens;
}

vector<Document> readDocuments(const string& filename) {
    vector<Document> docs;

    string text = readWholeFile(filename);
    if (text.empty()) {
        cerr << "Could not read file: " << filename << endl;
        return docs;
    }

    size_t i = 0;
    while (i < text.size()) {
        if (text[i] == '{') {
            size_t objStart = i;
            int depth = 1;
            size_t j = i + 1;
            while (j < text.size() && depth > 0) {
                if (text[j] == '{') depth++;
                else if (text[j] == '}') depth--;
                j++;
            }
            size_t objEnd = j - 1;

            Document doc;
            doc.docId = extractDocId(text, objStart, objEnd);
            doc.tokens = extractTokens(text, objStart, objEnd);

            // ADDED: Extract the document URL
            doc.url = extractString(text, objStart, objEnd, "url");

            // ADDED: Extract metadata fields from the meta object
            doc.meta.crawled_at =
                extractMetaValue(text, objStart, objEnd, "crawled_at");

            doc.meta.content_length =
                extractMetaInt(text, objStart, objEnd, "content_length");

            doc.meta.status =
                extractMetaValue(text, objStart, objEnd, "status");

            doc.meta.depth =
                extractMetaInt(text, objStart, objEnd, "depth");

            if (doc.docId != -1) {
                docs.push_back(doc);
            }

            i = j; // continue scan
        } else {
            i++;
        }
    }

    return docs;
}