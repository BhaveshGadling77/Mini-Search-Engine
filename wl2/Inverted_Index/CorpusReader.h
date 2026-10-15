#ifndef CORPUSREADER_H
#define CORPUSREADER_H

#include <string>
#include <vector>
using namespace std;

struct Document {
    int docId;
    string title;
    string url;
    string text;
    vector<string> tokens;
};

vector<Document> readDocuments(const string& filename);

#endif
