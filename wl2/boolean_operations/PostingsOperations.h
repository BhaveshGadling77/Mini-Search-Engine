#ifndef POSTINGSOPERATIONS_H
#define POSTINGSOPERATIONS_H

#include "Posting.h"
#include <vector>

using namespace std;

/**
 * @brief PostingsOperations provides Boolean set operations on vector-backed PostingList instances.
 *
 * Implements high-performance two-pointer sorted merge algorithms:
 * 1. Intersection (AND): Elements appearing in both lists in O(n + m) linear time.
 * 2. Union (OR): Elements appearing in either list without duplicates in O(n + m) linear time.
 * 3. Difference (NOT): Elements appearing in list A but not in list B in O(n + m) linear time.
 * 4. Intersection with Skips: Accelerated AND using O(sqrt(n)) index jump steps on dynamic arrays.
 */
class PostingsOperations {
public:
    static PostingList intersect(
        const PostingList& a,
        const PostingList& b
    );

    static PostingList union_(
        const PostingList& a,
        const PostingList& b
    );

    static PostingList difference(
        const PostingList& a,
        const PostingList& b
    );

    static PostingList intersect_with_skips(
        const PostingList& a,
        const PostingList& b
    );

    // Convenience extractors for downstream query parser / ranking integration
    static vector<int> extract_doc_ids(const PostingList& list);
    static vector<int> boolean_and(const PostingList& a, const PostingList& b);
    static vector<int> boolean_or(const PostingList& a, const PostingList& b);
    static vector<int> boolean_not(const PostingList& a, const PostingList& b);
};

#endif // POSTINGSOPERATIONS_H
