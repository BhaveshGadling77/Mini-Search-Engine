#include "HashMap.h"

HashMap::HashMap() {
    for (int i = 0; i < TABLE_SIZE; i++) {
        table[i] = nullptr;
    }
}

HashMap::~HashMap() {
    for (int i = 0; i < TABLE_SIZE; i++) {
        Entry* cur = table[i];
        while (cur != nullptr) {
            Entry* temp = cur;
            cur = cur->next;
            delete temp->value;
            delete temp;
        }
    }
}


int HashMap::hashFunction(const string& key) const {
    unsigned long hash = 5381;
    for (size_t i = 0; i < key.length(); i++) {
        hash = hash * 33 + key[i];
    }
    return hash % TABLE_SIZE;
}

PostingList* HashMap::insert(const string& word) {
    int index = hashFunction(word);

    Entry* cur = table[index];
    while (cur != nullptr) {
        if (cur->key == word) {
            return cur->value;
        }
        cur = cur->next;
    }

    // word nnot fount, create new entry and put at starting
    Entry* newEntry = new Entry();
    newEntry->key = word;
    newEntry->value = new PostingList();
    newEntry->next = table[index];
    table[index] = newEntry;

    return newEntry->value;
}

PostingList* HashMap::get(const string& word) const {
    int index = hashFunction(word);

    Entry* cur = table[index];
    while (cur != nullptr) {
        if (cur->key == word) {
            return cur->value;
        }
        cur = cur->next;
    }

    return nullptr; //not found
}

bool HashMap::search(const string& word) const {
    return get(word) != nullptr;
}

void HashMap::update(const string& word, int docId, int pos) {
    PostingList* list = insert(word); // get existing list or create new one
    list->addOccurrence(docId, pos);
}

void HashMap::displayAll() const {
    for (int i = 0; i < TABLE_SIZE; i++) {
        Entry* cur = table[i];
        while (cur != nullptr) {
            cout << "Word: " << cur->key << endl;
            cur->value->print();
            cur = cur->next;
        }
    }
}