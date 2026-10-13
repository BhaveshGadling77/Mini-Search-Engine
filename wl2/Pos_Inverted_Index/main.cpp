#include <iostream>
#include "HashMap.h"
#include "JsonReader.h"
using namespace std;

int main() {
    string filename = "sample_input.json";

    vector<Document> docs = readDocuments(filename);
    cout << "Loaded " << docs.size() << " documents from " << filename << endl << endl;

    HashMap index;

    //positiona inverted index
    for (size_t d = 0; d < docs.size(); d++) {
        Document& doc = docs[d];
        for (size_t pos = 0; pos < doc.tokens.size(); pos++) {
            index.update(doc.tokens[pos], doc.docId, (int)pos);
        }
    }

    cout << "===== POSITIONAL INVERTED INDEX =====" << endl << endl;
    index.displayAll();

    //sample output
    cout << "search(\"fox\") = " << index.search("fox") << endl;
    cout << "search(\"notaword\") = " << index.search("notaword") << endl;

    //user inputs
    cout << endl << "Enter a word to look up (or 'exit' to quit):" << endl;
    string word;
    while (cout << "> " && cin >> word) {
        if (word == "exit") break;

        if (index.search(word)) {
            cout << "Word: " << word << endl;
            index.get(word)->print();
        } else {
            cout << "\"" << word << "\" not found in index" << endl;
        }
    }

    return 0;
}