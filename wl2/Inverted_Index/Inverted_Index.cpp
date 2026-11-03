#include "Inverted_Index.h"
#include "Posting.h"
#include "../lib/src/include/text_processing.h"

// positional inverted index
void Inverted_Index::build(const vector<Document>& docs) {
    for (size_t d = 0; d < docs.size(); d++) {
        const Document& doc = docs[d];
        const string text = doc.text.empty() ? [&doc]() {
            string joined;
            for (const auto &token : doc.tokens) { if (!joined.empty()) joined += ' '; joined += token; }
            return joined;
        }() : doc.text;


        string sentence;
        int position = 0;
        auto index_sentence = [&]() {
            const auto words = wl2::tokenize(sentence);
            for (const auto& word : words) {
                // Keep stopwords in positional postings for exact phrase
                // checks; ordinary term lookup still filters them out.
                const string term = wl2::is_stopword(word) ? word : wl2::lemmatize(word);
                index.update(term, doc.docId, position++);
            }
            if (!words.empty())
                ++position;
            sentence.clear();
        };

        for (char c : text) {
            sentence.push_back(c);
            if (c == '.' || c == '!' || c == '?')
                index_sentence();
        }
        index_sentence();
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

PostingList* Inverted_Index::get_positional(const string& word) {
    return index.get(word);
}
