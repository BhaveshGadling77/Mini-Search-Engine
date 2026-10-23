
#ifndef POSTING_H
#define POSTING_H

#include <iostream>
#include <vector>
using namespace std;

struct Posting {
    int docId;
    vector<int> positions;
    int frequency;
};

class PostingList {
  private:
    vector<Posting> postings;

public:
    PostingList();

    void addOccurrence(int docId, int pos);

    // Append an already-formed posting in document-ID order. The caller must
    // ensure its docId is greater than the current last posting's docId.
    void appendSortedPosting(const Posting &posting);

    const vector<Posting>& get_all() const;

    void print() const;

    //to sort postings by document ID
    // void sortPostings();
};

#endif
