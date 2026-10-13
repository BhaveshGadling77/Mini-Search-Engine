#include "JsonReader.h"
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
    size_t i = colonPos + 1;
    while (i < text.size() && !isdigit(text[i]) && text[i] != '-') i++;

    size_t start = i;
    while (i < text.size() && (isdigit(text[i]) || text[i] == '-')) i++;

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