#ifndef INVERTED_INDEX_H
#define INVERTED_INDEX_H

#include "HashMap.h"
#include "CorpusReader.h"

class Inverted_Index {
private:
    HashMap index;

public:
    void build(const vector<Document>& docs);
    void displayAll() const;
    bool search(const string& word) const;
    PostingList* get(const string& word);
};

#endif