#include "PostingsOperations.h"

#include <algorithm>
#include <cmath>

namespace {

void append_posting(PostingList &destination, const Posting &posting) {
    destination.appendSortedPosting(posting);
}

} // namespace

PostingList PostingsOperations::intersect(const PostingList &a, const PostingList &b) {
    PostingList result;
    const std::vector<Posting> &left = a.get_all();
    const std::vector<Posting> &right = b.get_all();
    size_t i = 0, j = 0;

    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            append_posting(result, left[i]);
            ++i;
            ++j;
        } else if (left[i].docId < right[j].docId) {
            ++i;
        } else {
            ++j;
        }
    }
    return result;
}

PostingList PostingsOperations::union_(const PostingList &a, const PostingList &b) {
    PostingList result;
    const std::vector<Posting> &left = a.get_all();
    const std::vector<Posting> &right = b.get_all();
    size_t i = 0, j = 0;

    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            append_posting(result, left[i++]);
            ++j;
        } else if (left[i].docId < right[j].docId) {
            append_posting(result, left[i++]);
        } else {
            append_posting(result, right[j++]);
        }
    }
    while (i < left.size())
        append_posting(result, left[i++]);
    while (j < right.size())
        append_posting(result, right[j++]);
    return result;
}

PostingList PostingsOperations::union_with_skips(const PostingList &a, const PostingList &b) {
    PostingList result;
    const auto &left = a.get_all();
    const auto &right = b.get_all();
    size_t i = 0, j = 0;

    // Seek to the next matching document ID in the opposite list. Entries
    // skipped over still belong in the union, so append those ranges as well.
    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            append_posting(result, left[i]);
            ++i;
            ++j;
        } else if (left[i].docId < right[j].docId) {
            const auto next = std::lower_bound(
                left.begin() + static_cast<std::ptrdiff_t>(i), left.end(), right[j].docId,
                [](const Posting &posting, int id) { return posting.docId < id; });
            while (left.begin() + static_cast<std::ptrdiff_t>(i) != next)
                append_posting(result, left[i++]);
        } else {
            const auto next = std::lower_bound(
                right.begin() + static_cast<std::ptrdiff_t>(j), right.end(), left[i].docId,
                [](const Posting &posting, int id) { return posting.docId < id; });
            while (right.begin() + static_cast<std::ptrdiff_t>(j) != next)
                append_posting(result, right[j++]);
        }
    }
    while (i < left.size()) append_posting(result, left[i++]);
    while (j < right.size()) append_posting(result, right[j++]);
    return result;
}

PostingList PostingsOperations::difference(const PostingList &a, const PostingList &b) {
    PostingList result;
    const std::vector<Posting> &left = a.get_all();
    const std::vector<Posting> &right = b.get_all();
    size_t i = 0, j = 0;

    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            ++i;
            ++j;
        } else if (left[i].docId < right[j].docId) {
            append_posting(result, left[i++]);
        } else {
            ++j;
        }
    }
    while (i < left.size())
        append_posting(result, left[i++]);
    return result;
}

PostingList PostingsOperations::intersect_with_skips(const PostingList &a, const PostingList &b) {
    return union_with_skips(a, b);
}

std::vector<int> PostingsOperations::extract_doc_ids(const PostingList &list) {
    std::vector<int> ids;
    ids.reserve(list.get_all().size());
    for (const Posting &posting : list.get_all())
        ids.push_back(posting.docId);
    return ids;
}

PostingList PostingsOperations::intersect_with_sqrt_skips(const PostingList &a, const PostingList &b) {
    return union_with_skips(a, b);
}

PostingList PostingsOperations::intersect_with_fixed_skips(
    const PostingList &a, const PostingList &b, int interval) {
    (void)interval;
    return union_with_skips(a, b);
}

PostingList PostingsOperations::intersect_with_exponential_skips(
    const PostingList &a, const PostingList &b) {
    return union_with_skips(a, b);
}
