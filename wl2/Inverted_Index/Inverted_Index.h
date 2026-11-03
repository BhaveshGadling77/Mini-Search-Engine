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
    // Positional lookup includes stopwords; regular term lookup intentionally does not.
    PostingList* get_positional(const string& word);
};

#endif
