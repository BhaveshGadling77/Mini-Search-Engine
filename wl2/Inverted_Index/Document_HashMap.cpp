#include "Document_HashMap.h"
#include <iostream>

using namespace std;

// Constructor: create an empty hash table
DocumentHashMap::DocumentHashMap()
    : table(DOCUMENT_TABLE_SIZE, nullptr), entryCount(0) {
}

// Destructor: free all dynamically allocated entries
DocumentHashMap::~DocumentHashMap() {
    for (size_t i = 0; i < table.size(); i++) {
        Entry* current = table[i];

        while (current != nullptr) {
            Entry* temp = current;
            current = current->next;
            delete temp;
        }
    }
}

// Hash function: find the bucket for a document ID
int DocumentHashMap::hashFunction(int docId) const {
    return static_cast<unsigned int>(docId) % table.size();
}

// Insert a document or update it if the ID already exists
void DocumentHashMap::insert(int docId, const DocumentInfo& document) {
    int index = hashFunction(docId);

    Entry* current = table[index];

    // Check whether this document ID already exists
    while (current != nullptr) {
        if (current->key == docId) {
            current->value = document;
            return;
        }

        current = current->next;
    }

    // Create a new entry for the document
    Entry* newEntry = new Entry;
    newEntry->key = docId;
    newEntry->value = document;
    newEntry->next = table[index];

    // Add the entry at the beginning of the linked list
    table[index] = newEntry;
    entryCount++;

    // Increase the table size when it becomes too full
    if (entryCount > static_cast<int>(table.size() * 0.75)) {
        rehash();
    }
}

// Retrieve a document using its ID
DocumentInfo* DocumentHashMap::get(int docId) {
    int index = hashFunction(docId);

    Entry* current = table[index];

    while (current != nullptr) {
        if (current->key == docId) {
            return &(current->value);
        }

        current = current->next;
    }

    // Return nullptr if the document does not exist
    return nullptr;
}

// Check whether a document ID exists
bool DocumentHashMap::search(int docId) const {
    int index = hashFunction(docId);

    Entry* current = table[index];

    while (current != nullptr) {
        if (current->key == docId) {
            return true;
        }

        current = current->next;
    }

    return false;
}

// Increase the table size and redistribute existing entries
void DocumentHashMap::rehash() {
    vector<Entry*> oldTable = table;

    // Create a larger table with empty buckets
    table.assign(oldTable.size() * 2 + 1, nullptr);

    // Move existing entries into their new buckets
    for (size_t i = 0; i < oldTable.size(); i++) {
        Entry* current = oldTable[i];

        while (current != nullptr) {
            Entry* nextEntry = current->next;

            int newIndex = hashFunction(current->key);

            current->next = table[newIndex];
            table[newIndex] = current;

            current = nextEntry;
        }
    }
}

// Display all stored documents
void DocumentHashMap::displayAll() const {
    for (size_t i = 0; i < table.size(); i++) {
        Entry* current = table[i];

        while (current != nullptr) {
            cout << "Document ID: " << current->key << endl;
            cout << "Meta:" << endl;
            cout << "URL: " << current->value.url << endl;

            cout << "Crawled At: "
                 << current->value.meta.crawled_at << endl;

            cout << "Content Length: "
                 << current->value.meta.content_length << endl;

            cout << "Status: "
                 << current->value.meta.status << endl;

            cout << "Depth: "
                 << current->value.meta.depth << endl;

            cout << "-----------------------------" << endl;

            current = current->next;
        }
    }
}