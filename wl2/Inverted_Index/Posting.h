
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
    //PostingList();

    void addOccurrence(int docId, int pos);

    const vector<Posting>& get_all() const;

    void print() const;

    //to sort postings by document ID
    void sortPostings();
};

#endif
