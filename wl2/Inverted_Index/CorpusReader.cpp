#include "CorpusReader.h"
#include <cctype>
#include <fstream>
#include <iostream>
#include <sstream>

static string extractString(const string &text, size_t start, size_t end,
                            const string &key);

// ADDED: Extract a metadata value from the meta object
static string extractMetaValue(const string& text, size_t objStart,
                               size_t objEnd, const string& key) {
    size_t metaPos = text.find("\"meta\"", objStart);
    if (metaPos == string::npos || metaPos > objEnd) return "";

    size_t metaStart = text.find('{', metaPos);
    if (metaStart == string::npos || metaStart > objEnd) return "";

    size_t metaEnd = text.find('}', metaStart);
    if (metaEnd == string::npos || metaEnd > objEnd) return "";
    const string meta = text.substr(metaStart, metaEnd - metaStart + 1);
    return extractString(meta, 0, meta.size(), key);
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

static void appendUtf8CodePoint(string &value, unsigned int codepoint) {
    if (codepoint == 0) {
        value.push_back(' ');
        return;
    }
    if (codepoint < 0x20 && codepoint != '\n' && codepoint != '\r' && codepoint != '\t') {
        value.push_back(' ');
        return;
    }
    if (codepoint <= 0x7F) {
        value.push_back(static_cast<char>(codepoint));
        return;
    }
    if (codepoint <= 0x7FF) {
        value.push_back(static_cast<char>(0xC0 | ((codepoint >> 6) & 0x1F)));
        value.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
        return;
    }
    if (codepoint <= 0xFFFF) {
        value.push_back(static_cast<char>(0xE0 | ((codepoint >> 12) & 0x0F)));
        value.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        value.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
        return;
    }
    if (codepoint <= 0x10FFFF) {
        value.push_back(static_cast<char>(0xF0 | ((codepoint >> 18) & 0x07)));
        value.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3F)));
        value.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        value.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    }
}

static void appendUnicodeEscape(string &value, const string &text, size_t &i, size_t end) {
    if (i + 4 > end) {
        if (i < end) value.push_back(text[i++]);
        return;
    }

    unsigned int codepoint = 0;
    for (int shift = 12; shift >= 0; shift -= 4) {
        const char ch = text[i++];
        int digit = 0;
        if (ch >= '0' && ch <= '9') {
            digit = ch - '0';
        } else if (ch >= 'a' && ch <= 'f') {
            digit = ch - 'a' + 10;
        } else if (ch >= 'A' && ch <= 'F') {
            digit = ch - 'A' + 10;
        } else {
            --i;
            value.push_back(ch);
            return;
        }
        codepoint |= static_cast<unsigned int>(digit) << shift;
    }

    if (codepoint >= 0xD800 && codepoint <= 0xDBFF && i + 6 <= end &&
        text[i] == '\\' && text[i + 1] == 'u') {
        size_t surrogateStart = i + 2;
        unsigned int lowSurrogate = 0;
        bool validLowSurrogate = true;
        for (int shift = 12; shift >= 0; shift -= 4) {
            if (surrogateStart + 4 > end) {
                validLowSurrogate = false;
                break;
            }
            const char ch = text[surrogateStart++];
            int digit = 0;
            if (ch >= '0' && ch <= '9') {
                digit = ch - '0';
            } else if (ch >= 'a' && ch <= 'f') {
                digit = ch - 'a' + 10;
            } else if (ch >= 'A' && ch <= 'F') {
                digit = ch - 'A' + 10;
            } else {
                validLowSurrogate = false;
                break;
            }
            lowSurrogate |= static_cast<unsigned int>(digit) << shift;
        }
        if (validLowSurrogate && lowSurrogate >= 0xDC00 && lowSurrogate <= 0xDFFF) {
            codepoint = 0x10000 + (((codepoint - 0xD800) << 10) | (lowSurrogate - 0xDC00));
            i += 6;
        }
    }

    appendUtf8CodePoint(value, codepoint);
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
            case 'u':
                appendUnicodeEscape(value, text, i, end);
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
    const string text = readWholeFile(filename);
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
            bool inString = false;
            bool escaped = false;
            while (j < text.size() && depth > 0) {
                const char c = text[j];
                if (inString) {
                    if (escaped) escaped = false;
                    else if (c == '\\') escaped = true;
                    else if (c == '"') inString = false;
                } else if (c == '"') {
                    inString = true;
                } else if (c == '{') {
                    depth++;
                } else if (c == '}') {
                    depth--;
                }
                j++;
            }
            size_t objEnd = j - 1;
            const string object = text.substr(objStart, j - objStart);

            Document doc;
            doc.docId = extractDocId(text, objStart, objEnd);
            doc.tokens = extractTokens(object, 0, object.size());
            doc.title = extractString(object, 0, object.size(), "title");
            doc.url = extractString(object, 0, object.size(), "url");
            doc.text = extractString(object, 0, object.size(), "text");

            // ADDED: Extract metadata fields from the meta object
            doc.meta.crawled_at =
                extractMetaValue(text, objStart, objEnd, "crawled_at");

            doc.meta.content_length =
                extractMetaInt(text, objStart, objEnd, "content_length");

            doc.meta.status =
                extractMetaValue(text, objStart, objEnd, "status");

            doc.meta.depth =
                extractMetaInt(text, objStart, objEnd, "depth");

            i = j; // continue scan
            if (doc.docId != -1)
                docs.push_back(std::move(doc));
        } else {
            i++;
        }
    }

    return docs;
}
