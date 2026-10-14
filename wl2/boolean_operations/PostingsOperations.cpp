#include "PostingsOperations.h"
#include <cmath>

using namespace std;

/*
 * Intersection (Boolean AND) — Two-pointer linear merge
 *
 * Both lists are sorted by docId. We walk two pointers i, j forward:
 *   - If a[i] == b[j]: match found, emit and advance both.
 *   - If a[i] <  b[j]: a[i] cannot match anything remaining in b, advance i.
 *   - If a[i] >  b[j]: b[j] cannot match anything remaining in a, advance j.
 * Time:  O(n + m)   — each pointer advances at most n or m times.
 * Space: O(1) auxiliary beyond the output list.
 */
PostingList PostingsOperations::intersect(const PostingList& a, const PostingList& b) {
    PostingList result;
    if (a.empty() || b.empty()) {
        return result;
    }

    const vector<Posting>& vecA = a.get_all();
    const vector<Posting>& vecB = b.get_all();

    size_t i = 0;
    size_t j = 0;

    while (i < vecA.size() && j < vecB.size()) {
        int docA = vecA[i].get_doc_id();
        int docB = vecB[j].get_doc_id();

        if (docA == docB) {
            result.add(vecA[i]);
            i++;
            j++;
        } else if (docA < docB) {
            i++;
        } else {
            j++;
        }
    }

    return result;
}

/*
 * Union (Boolean OR) — Two-pointer linear merge
 *
 * Merges two sorted lists into one sorted list without duplicate docIds.
 *   - If a[i] == b[j]: emit once (from 'a'), advance both.
 *   - If a[i] <  b[j]: emit a[i], advance i.
 *   - If a[i] >  b[j]: emit b[j], advance j.
 *   - Drain remaining elements from whichever list is not exhausted.
 * Time:  O(n + m)
 * Space: O(1) auxiliary beyond the output list.
 */
PostingList PostingsOperations::union_(const PostingList& a, const PostingList& b) {
    PostingList result;

    const vector<Posting>& vecA = a.get_all();
    const vector<Posting>& vecB = b.get_all();

    size_t i = 0;
    size_t j = 0;

    while (i < vecA.size() && j < vecB.size()) {
        int docA = vecA[i].get_doc_id();
        int docB = vecB[j].get_doc_id();

        if (docA == docB) {
            result.add(vecA[i]);
            i++;
            j++;
        } else if (docA < docB) {
            result.add(vecA[i]);
            i++;
        } else {
            result.add(vecB[j]);
            j++;
        }
    }

    while (i < vecA.size()) {
        result.add(vecA[i]);
        i++;
    }

    while (j < vecB.size()) {
        result.add(vecB[j]);
        j++;
    }

    return result;
}

/*
 * Difference (Boolean NOT) — Two-pointer linear scan
 *
 * Emits documents from 'a' that do NOT appear in 'b' (A \ B).
 *   - If a[i] == b[j]: skip (document excluded by b), advance both.
 *   - If a[i] <  b[j]: a[i] is absent in b, emit it, advance i.
 *   - If a[i] >  b[j]: b[j] is irrelevant, advance j.
 *   - Drain remaining elements from 'a' (all absent in b).
 *
 * Time:  O(n + m)
 * Space: O(1) auxiliary beyond the output list.
 */
PostingList PostingsOperations::difference(const PostingList& a, const PostingList& b) {
    PostingList result;
    if (a.empty()) {
        return result;
    }

    const vector<Posting>& vecA = a.get_all();
    const vector<Posting>& vecB = b.get_all();

    size_t i = 0;
    size_t j = 0;

    while (i < vecA.size() && j < vecB.size()) {
        int docA = vecA[i].get_doc_id();
        int docB = vecB[j].get_doc_id();

        if (docA == docB) {
            i++;
            j++;
        } else if (docA < docB) {
            result.add(vecA[i]);
            i++;
        } else {
            j++;
        }
    }

    while (i < vecA.size()) {
        result.add(vecA[i]);
        i++;
    }

    return result;
}

/*
 * Intersection with Skip Pointers - Index-jump two-pointer merge probabilistically
 *
 * Same correctness as intersect(), but when one pointer trails behind,
 * instead of stepping +1, we attempt a skip jump of size k = sqrt(N):
 *
 *   If docA < docB:
 *     If a[i + k] exists and a[i + k].docId <= docB:
 *       Jump i forward by k repeatedly until a[i + k].docId > docB.
 *       (All skipped elements have docId < docB, so none can be matches.)
 *     Else:
 *       Step i by 1 as usual.
 *
 * Why it produces the same result:
 *   Because the list is sorted, all documents between position i and i+k
 *   have docId strictly less than a[i+k].docId. Since a[i+k].docId <= docB,
 *   every skipped document has docId < docB and cannot match docB or any
 *   future element in b (which are all >= docB). So zero matches are missed.
 *
 * Time:  O(sqrt(n) + sqrt(m)) best case (sparse matches),
 *        O(n + m) worst case (dense matches, same as ordinary intersect).
 * Space: O(1) auxiliary beyond the output list.
*/ 
PostingList PostingsOperations::intersect_with_skips(const PostingList& a, const PostingList& b) {
    PostingList result;
    if (a.empty() || b.empty()) {
        return result;
    }

    const vector<Posting>& vecA = a.get_all();
    const vector<Posting>& vecB = b.get_all();

    size_t i = 0;
    size_t j = 0;

    // Skip step = floor(sqrt(N)), minimum 2
    size_t skipA = max<size_t>(2, static_cast<size_t>(sqrt(vecA.size())));
    size_t skipB = max<size_t>(2, static_cast<size_t>(sqrt(vecB.size())));

    while (i < vecA.size() && j < vecB.size()) {
        int docA = vecA[i].get_doc_id();
        int docB = vecB[j].get_doc_id();

        if (docA == docB) {
            result.add(vecA[i]);
            i++;
            j++;
        } else if (docA < docB) {
            // Try to skip forward in A
            if (i + skipA < vecA.size() && vecA[i + skipA].get_doc_id() <= docB) {
                while (i + skipA < vecA.size() && vecA[i + skipA].get_doc_id() <= docB) {
                    i += skipA;
                }
            } else {
                i++;
            }
        } else {
            // Try to skip forward in B
            if (j + skipB < vecB.size() && vecB[j + skipB].get_doc_id() <= docA) {
                while (j + skipB < vecB.size() && vecB[j + skipB].get_doc_id() <= docA) {
                    j += skipB;
                }
            } else {
                j++;
            }
        }
    }

    return result;
}

// convenience extractors
vector<int> PostingsOperations::extract_doc_ids(const PostingList& list) {
    vector<int> doc_ids;
    doc_ids.reserve(list.size());
    for (const auto& post : list.get_all()) {
        doc_ids.push_back(post.get_doc_id());
    }
    return doc_ids;
}

vector<int> PostingsOperations::boolean_and(const PostingList& a, const PostingList& b) {
    return extract_doc_ids(intersect(a, b));
}

vector<int> PostingsOperations::boolean_or(const PostingList& a, const PostingList& b) {
    return extract_doc_ids(union_(a, b));
}

vector<int> PostingsOperations::boolean_not(const PostingList& a, const PostingList& b) {
    return extract_doc_ids(difference(a, b));
}
