#ifndef DOCUMENT_HASHMAP_H
#define DOCUMENT_HASHMAP_H

#include <string>
#include <vector>

using namespace std;

constexpr int DOCUMENT_TABLE_SIZE = 211;

// Metadata associated with each document
struct DocumentMeta {
    string crawled_at;
    int content_length;
    string status;
    int depth;
};

// Stores URL and metadata together
struct DocumentInfo {
    string url;
    DocumentMeta meta;
};

class DocumentHashMap {
private:
    struct Entry {
        int key;              // doc_id
        DocumentInfo value;       // URL + metadata
        Entry* next;
    };

    vector<Entry*> table;
    int entryCount;

    int hashFunction(int docId) const;
    void rehash();

public:
    DocumentHashMap();
    ~DocumentHashMap();

    // Insert a new document or update an existing one
    void insert(int docId, const DocumentInfo& document);

    // Retrieve a document using doc_id
    DocumentInfo* get(int docId);

    // Check whether a document exists
    bool search(int docId) const;

    // Display all stored documents
    void displayAll() const;
};

#endif