#include "Inverted_Index.h"

// Build the positional inverted index
void Inverted_Index::build(const vector<Document>& docs) {
    for (size_t d = 0; d < docs.size(); d++) {
        const Document& doc = docs[d];

        for (size_t pos = 0; pos < doc.tokens.size(); pos++) {
            index.update(
                doc.tokens[pos],
                doc.docId,
                (int)pos
            );
        }
    }
}

// Display the complete inverted index
void Inverted_Index::displayAll() const {
    index.displayAll();
}

// Search for a word
bool Inverted_Index::search(const string& word) const {
    return index.search(word);
}

// Retrieve the posting list for a word
PostingList* Inverted_Index::get(const string& word) {
    return index.get(word);
}