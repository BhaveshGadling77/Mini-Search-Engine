#include "CorpusReader.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cctype>

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

static string extractString(const string& text, size_t start, size_t end, const string& key) {
    size_t keyPos = text.find("\"" + key + "\"", start);
    if (keyPos == string::npos || keyPos > end) return "";
    size_t quote = text.find('"', text.find(':', keyPos) + 1);
    if (quote == string::npos || quote > end) return "";
    string value;
    for (size_t i = quote + 1; i < end; ++i) {
        if (text[i] == '"') break;
        if (text[i] == '\\' && i + 1 < end) { ++i; value += text[i]; }
        else value += text[i];
    }
    return value;
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
            doc.title = extractString(text, objStart, objEnd, "title");
            doc.url = extractString(text, objStart, objEnd, "url");
            doc.text = extractString(text, objStart, objEnd, "text");
            doc.tokens = extractTokens(text, objStart, objEnd);
            if (doc.tokens.empty() && !doc.text.empty()) {
                istringstream words(doc.text);
                string word;
                while (words >> word) doc.tokens.push_back(word);
            }

            if (doc.docId != -1) {
                docs.push_back(doc);
            }

            i = j; //continue scan
        } else {
            i++;
        }
    }

    return docs;
}
