#ifndef HASHMAP_H
#define HASHMAP_H

#include <string>
#include "Posting.h"
using namespace std;

class HashMap {
private:
    static const int TABLE_SIZE = 211;

    struct Entry {
        string key;
        PostingList* value;
        Entry* next;
    };

    Entry* table[TABLE_SIZE];

    int hashFunction(const string& key) const;

public:
    HashMap();
    ~HashMap();

    PostingList* insert(const string& word);
    PostingList* get(const string& word) const;

    // search, true if exists
    bool search(const string& word) const;

    //add occurance doc + pos and insert word f=if not exists
    void update(const string& word, int docId, int pos);

    void displayAll() const;
};

#endif