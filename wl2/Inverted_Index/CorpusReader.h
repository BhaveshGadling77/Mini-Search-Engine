#ifndef CORPUS_READER_H
#define CORPUS_READER_H

#include <string>
#include <vector>

using namespace std;

struct CorpusMeta {
    string crawled_at;
    int content_length;
    string status;
    int depth;
};
// Read documents from a corpus file
struct Document {
    int docId;
    string url;
    string text;
    vector<string> tokens;
    CorpusMeta meta;
};

vector<Document> readDocuments(const string& filename);

#endif