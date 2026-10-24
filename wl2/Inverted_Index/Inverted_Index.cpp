#include "Inverted_Index.h"
#include "Posting.h"
#include "../lib/src/include/text_processing.h"

// Build the positional inverted index
void Inverted_Index::build(const vector<Document>& docs) {
    for (size_t d = 0; d < docs.size(); d++) {
        const Document& doc = docs[d];

        const auto terms = wl2::process_text(doc.text.empty() ? [&doc]() {
            string joined;
            for (const auto &token : doc.tokens) { if (!joined.empty()) joined += ' '; joined += token; }
            return joined;
        }() : doc.text);
        for (size_t pos = 0; pos < terms.size(); pos++) {
            index.update(
                terms[pos],
                doc.docId,
                (int)pos
            );
        }
    }
    index.sortAllPostingLists();
}

// Display the complete inverted index
void Inverted_Index::displayAll() const {
    index.displayAll();
}

// Search for a word
bool Inverted_Index::search(const string& word) const {
    if (wl2::is_stopword(word)) return false;
    return index.search(wl2::lemmatize(word));
}

// Retrieve the posting list for a word
PostingList* Inverted_Index::get(const string& word) {
    if (wl2::is_stopword(word)) return nullptr;
    return index.get(wl2::lemmatize(word));
}
