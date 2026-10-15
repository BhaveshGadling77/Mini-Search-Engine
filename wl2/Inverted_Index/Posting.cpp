
#include "Posting.h"
#include <iostream>
#include <algorithm>
using namespace std;

/*
// Constructor
PostingList::PostingList() {
} */

void PostingList::sortPostings() {
    sort(postings.begin(), postings.end(),
         [](const Posting& a, const Posting& b) {
             return a.docId < b.docId;
         });
}

// Add an occurrence of a word
void PostingList::addOccurrence(int docId, int pos) {

    // Check if document already exists
    for (size_t i = 0; i < postings.size(); i++) {
        if (postings[i].docId == docId) {
            postings[i].positions.push_back(pos);
            postings[i].frequency++;
            return;
        }
    }

    // Document not found: create a new posting
    Posting newPost;
    newPost.docId = docId;
    newPost.positions.push_back(pos);
    newPost.frequency = 1;

   /* // Find the correct position by docId
    auto it = postings.begin();

    while (it != postings.end() && it->docId < docId) {
        it++;
    }

    // Insert in ascending order
    postings.insert(it, newPost);
    */
   postings.push_back(newPost);
}

const vector<Posting>& PostingList::get_all() const {
    return postings;
}

// Print the posting list
void PostingList::print() const {

    for (size_t i = 0; i < postings.size(); i++) {

        cout << "    Doc ID: "
             << postings[i].docId << endl;

        cout << "    Positions: [";

        for (size_t j = 0;
             j < postings[i].positions.size(); j++) {

            cout << postings[i].positions[j];

            if (j + 1 < postings[i].positions.size()) {
                cout << ", ";
            }
        }

        cout << "]" << endl;

        cout << "    Frequency: "
             << postings[i].frequency << endl << endl;
    }
}
