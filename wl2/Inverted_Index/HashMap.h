#ifndef HASHMAP_H
#define HASHMAP_H

#include <string>
#include <vector>
//#include <iostream>
#include "Posting.h"
using namespace std;

constexpr int TABLE_SIZE = 211;

class HashMap {
private:
    // Each bucket stores the head of a linked list
    struct Entry {
        string key;
        PostingList* value;
        Entry* next;
    };

    vector<Entry*> table;
    int entryCount;

    int hashFunction(const string& key) const;

    // Increase table size when it becomes too full
    void rehash();

public:
    HashMap();
    ~HashMap();

    PostingList* insert(const string& word);
    PostingList* get(const string& word) const;

    // search, true if exists
    bool search(const string& word) const;

    // add occurrence doc + pos and insert word if not exists
    void update(const string& word, int docId, int pos);

    void displayAll() const;
};

#endif
