
#include "HashMap.h"
#include <iostream>

HashMap::HashMap() : table(TABLE_SIZE, nullptr), entryCount(0) {}

HashMap::~HashMap() {
    for (size_t i = 0; i < table.size(); i++) {
        Entry *cur = table[i];

        while (cur != nullptr) {
            Entry *temp = cur;
            cur = cur->next;

            delete temp->value;
            delete temp;
        }
    }
}

int HashMap::hashFunction(const string &key) const {
    unsigned long hash = 5381;

    for (size_t i = 0; i < key.length(); i++) {
        hash = hash * 33 + static_cast<unsigned char>(key[i]);
    }

    return hash % table.size();
}

PostingList *HashMap::insert(const string &word) {
    int index = hashFunction(word);

    Entry *cur = table[index];

    while (cur != nullptr) {
        if (cur->key == word) {
            return cur->value;
        }

        cur = cur->next;
    }

    // word not found, create new entry and put at starting
    Entry *newEntry = new Entry();
    newEntry->key = word;
    newEntry->value = new PostingList();
    newEntry->next = table[index];
    table[index] = newEntry;

    entryCount++;

    // increase table size when it becomes too full
    if (static_cast<double>(entryCount) / table.size() > 0.75) {
        rehash();
    }

    return newEntry->value;
}

PostingList *HashMap::get(const string &word) const {
    int index = hashFunction(word);

    Entry *cur = table[index];

    while (cur != nullptr) {
        if (cur->key == word) {
            return cur->value;
        }

        cur = cur->next;
    }

    return nullptr; // not found
}

bool HashMap::search(const string &word) const {
    return get(word) != nullptr;
}

void HashMap::update(const string &word, int docId, int pos) {
    PostingList *list = insert(word); // get existing list or create new one
    list->addOccurrence(docId, pos);
}

void HashMap::displayAll() const {
    for (size_t i = 0; i < table.size(); i++) {
        Entry *cur = table[i];

        while (cur != nullptr) {
            cout << "Word: " << cur->key << endl;
            cur->value->print();

            cur = cur->next;
        }
    }
}

// increase table size and rearrange existing entries
void HashMap::rehash() {
    vector<Entry *> oldTable = table;

    table.assign(oldTable.size() * 2, nullptr);

    for (size_t i = 0; i < oldTable.size(); i++) {
        Entry *cur = oldTable[i];

        while (cur != nullptr) {
            Entry *nextEntry = cur->next;

            int index = hashFunction(cur->key);

            cur->next = table[index];
            table[index] = cur;

            cur = nextEntry;
        }
    }
}

void HashMap::sortAllPostingLists() {
    for (size_t i = 0; i < table.size(); i++) {
        Entry* current = table[i];

        while (current != nullptr) {
            current->value->sortPostings();
            current = current->next;
        }
    }
}