
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
    void appendSortedPosting(const Posting &posting);

    void reserve(size_t capacity);

    void appendSortedRange(
        const vector<Posting>& source,
        size_t start,
        size_t end
    );

    const vector<Posting>& get_all() const;

    void print() const;
};

#endif
