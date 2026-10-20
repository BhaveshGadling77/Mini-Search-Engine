#ifndef POSTINGSOPERATIONS_H
#define POSTINGSOPERATIONS_H

#include "../Inverted_Index/Posting.h"
#include <vector>

class PostingsOperations {
  public:
    // Boolean operations consume and return the inverted index's PostingList type.
    static PostingList intersect(const PostingList &a, const PostingList &b);
    static PostingList union_(const PostingList &a, const PostingList &b);
    static PostingList difference(const PostingList &a, const PostingList &b);
    static PostingList intersect_with_skips(const PostingList &a, const PostingList &b);

    static std::vector<int> extract_doc_ids(const PostingList &list);
    static PostingList intersect_with_sqrt_skips(const PostingList& a, const PostingList& b);
    
    static PostingList intersect_with_fixed_skips( const PostingList& a, const PostingList& b, int interval);
    
    static PostingList intersect_with_exponential_skips( const PostingList& a, const PostingList& b);
};

#endif // POSTINGSOPERATIONS_H
