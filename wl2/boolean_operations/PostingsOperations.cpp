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

namespace {

/* A "skip pointer" sits at every index that is a multiple of `stride` and points
 * `stride` entries ahead. Nothing is stored: the pointers are implicit.
 *
 * Returns an index p >= i such that EVERY entry in [i, p) has docId < target.
 * The only way p moves past i is by following a skip pointer whose destination
 * docId is still strictly < target; since lists are sorted, every entry before
 * that destination is smaller still. Skipping can therefore never pass an entry
 * that belongs next to `target` in the merge, and never drops one either
 * (the caller copies [i, p) into the result).
 */
 size_t follow_fixed_skips(const std::vector<Posting> &list, size_t i, int target, size_t stride) {
    if (stride <= 1) return i;
    while (i % stride == 0 && i + stride < list.size() && list[i + stride].docId < target)
        i += stride;
    return i;
}

// probe i+1, i+2, i+4, ... then binary search the last window.
// Same guarantee: every entry in [i, p) has docId < target.
size_t follow_exponential_skips(const std::vector<Posting> &list, size_t i, int target) {
    size_t step = 1;
    size_t lo = i; // invariant: list[lo].docId < target (caller checked for lo == i)
    while (lo + step < list.size() && list[lo + step].docId < target) {
        lo += step;
        step <<= 1;
    }
    size_t hi = std::min(lo + step, list.size()); // list[hi].docId >= target, or hi == size
    // Find first index in (lo, hi] with docId >= target.
    size_t first = lo + 1;
    while (first < hi) {
        size_t mid = first + (hi - first) / 2;
        if (list[mid].docId < target) first = mid + 1;
        else hi = mid;
    }
    return first;
}

enum class SkipKind { Fixed, Exponential };

PostingList union_skip_merge(const PostingList &a, const PostingList &b, SkipKind kind,
                             size_t left_stride, size_t right_stride) {
    PostingList result;
    const std::vector<Posting> &left = a.get_all();
    const std::vector<Posting> &right = b.get_all();
    size_t i = 0, j = 0;

    auto skip = [&](const std::vector<Posting> &list, size_t pos, int target, size_t stride) {
        return kind == SkipKind::Fixed ? follow_fixed_skips(list, pos, target, stride)
                                       : follow_exponential_skips(list, pos, target);
    };

    while (i < left.size() && j < right.size()) {
        const int l = left[i].docId;
        const int r = right[j].docId;
        if (l == r) {
            // Duplicate ID: emit once, keeping the left posting (same as union_).
            append_posting(result, left[i]);
            ++i;
            ++j;
        } else if (l < r) {
            // left[i] < right[j]: left[i] is certainly in the union. Jump ahead over
            // whole blocks that are still < right[j] and bulk-copy them.
            size_t next = skip(left, i, r, left_stride);
            if (next == i) next = i + 1;
            for (; i < next; ++i) append_posting(result, left[i]);
        } else {
            size_t next = skip(right, j, l, right_stride);
            if (next == j) next = j + 1;
            for (; j < next; ++j) append_posting(result, right[j]);
        }
    }
    while (i < left.size()) append_posting(result, left[i++]);
    while (j < right.size()) append_posting(result, right[j++]);
    return result;
}

size_t sqrt_stride(size_t n) {
    return std::max<size_t>(1, static_cast<size_t>(std::sqrt(static_cast<double>(n))));
}

} // namespace

PostingList PostingsOperations::union_with_skips(const PostingList &a, const PostingList &b) {
    return union_skip_merge(a, b, SkipKind::Fixed, sqrt_stride(a.get_all().size()),
                            sqrt_stride(b.get_all().size()));
}

PostingList PostingsOperations::union_with_fixed_skips(const PostingList &a, const PostingList &b,
                                                       int interval) {
    const size_t stride = interval > 1 ? static_cast<size_t>(interval) : 1;
    return union_skip_merge(a, b, SkipKind::Fixed, stride, stride);
}

PostingList PostingsOperations::union_with_exponential_skips(const PostingList &a,
                                                             const PostingList &b) {
    return union_skip_merge(a, b, SkipKind::Exponential, 0, 0);
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
    return union_with_fixed_skips(a, b, interval);
}

PostingList PostingsOperations::intersect_with_exponential_skips(
    const PostingList &a, const PostingList &b) {
    return union_with_exponential_skips(a, b);
}
