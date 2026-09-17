#ifndef JSONREADER_H
#define JSONREADER_H

#include <string>
#include <vector>
using namespace std;

struct Document {
    int docId;
    vector<string> tokens;
};

vector<Document> readDocuments(const string& filename);

#endif