<<<<<<< HEAD
#include "CorpusReader.h"
#include "HashMap.h"
#include <iostream>
=======
#include <iostream>
#include "CorpusReader.h"
#include "Document_HashMap.h"
#include "Inverted_Index.h"

>>>>>>> 4964a42fa731b5bbadfc149e4137ae033055247f
using namespace std;

int main() {
    string filename = "crawler.json";

    vector<Document> docs = readDocuments(filename);

    cout << "Loaded " << docs.size()
         << " documents from " << filename << endl << endl;

    // Create the document map and inverted index
    DocumentHashMap documentMap;
    Inverted_Index invertedIndex;

    // Store document information
    for (size_t d = 0; d < docs.size(); d++) {
        Document& doc = docs[d];

        DocumentInfo info;

        info.url = doc.url;
        info.meta.crawled_at = doc.meta.crawled_at;
        info.meta.content_length = doc.meta.content_length;
        info.meta.status = doc.meta.status;
        info.meta.depth = doc.meta.depth;

        documentMap.insert(doc.docId, info);
    }

    // Build the positional inverted index
    invertedIndex.build(docs);

    // Display the inverted index
    cout << "===== POSITIONAL INVERTED INDEX ====="
         << endl << endl;

    invertedIndex.displayAll();

    // Sample searches
    cout << endl;
    cout << "search(\"fox\") = "
         << invertedIndex.search("fox") << endl;

    cout << "search(\"notaword\") = "
         << invertedIndex.search("notaword") << endl;

    // Display all document information
    cout << endl
         << "===== DOCUMENT INFORMATION ====="
         << endl << endl;

    documentMap.displayAll();

    // User input for word searching
    cout << endl
         << "Enter a word to look up (or 'exit' to quit):"
         << endl;

    string word;

    while (cout << "> " && cin >> word) {
        if (word == "exit") {
            break;
        }

        if (invertedIndex.search(word)) {
            cout << endl;
            cout << "Word: " << word << endl;

            PostingList* postingList = invertedIndex.get(word);

            if (postingList != nullptr) {
                postingList->print();
            }
        } else {
            cout << "\"" << word
                 << "\" not found in index" << endl;
        }
    }

    return 0;
}