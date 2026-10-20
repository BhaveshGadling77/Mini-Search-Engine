#include "PostingsOperations.h"

#include <algorithm>
#include <cmath>

namespace {

void append_posting(PostingList &destination, const Posting &posting) {
    for (int position : posting.positions)
        destination.addOccurrence(posting.docId, position);
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
    PostingList result;
    const std::vector<Posting> &left = a.get_all();
    const std::vector<Posting> &right = b.get_all();
    if (left.empty() || right.empty())
        return result;

    const size_t skip_left = std::max<size_t>(2, static_cast<size_t>(std::sqrt(left.size())));
    const size_t skip_right = std::max<size_t>(2, static_cast<size_t>(std::sqrt(right.size())));
    size_t i = 0, j = 0;

    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            append_posting(result, left[i]);
            ++i;
            ++j;
        } else if (left[i].docId < right[j].docId) {
            if (i + skip_left < left.size() && left[i + skip_left].docId <= right[j].docId)
                i += skip_left;
            else
                ++i;
        } else {
            if (j + skip_right < right.size() && right[j + skip_right].docId <= left[i].docId)
                j += skip_right;
            else
                ++j;
        }
    }
    return result;
}

std::vector<int> PostingsOperations::extract_doc_ids(const PostingList &list) {
    std::vector<int> ids;
    ids.reserve(list.get_all().size());
    for (const Posting &posting : list.get_all())
        ids.push_back(posting.docId);
    return ids;
}

PostingList PostingsOperations::intersect_with_sqrt_skips(const PostingList &a, const PostingList &b) {
    return intersect_with_skips(a, b);
}

PostingList PostingsOperations::intersect_with_fixed_skips(
    const PostingList &a, const PostingList &b, int interval) {
    if (interval <= 1)
        return intersect(a, b);

    PostingList result;
    const auto &left = a.get_all();
    const auto &right = b.get_all();
    size_t i = 0, j = 0;
    const size_t step = static_cast<size_t>(interval);
    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            append_posting(result, left[i]);
            ++i;
            ++j;
        } else if (left[i].docId < right[j].docId) {
            if (i + step < left.size() && left[i + step].docId <= right[j].docId)
                i += step;
            else
                ++i;
        } else {
            if (j + step < right.size() && right[j + step].docId <= left[i].docId)
                j += step;
            else
                ++j;
        }
    }
    return result;
}

PostingList PostingsOperations::intersect_with_exponential_skips(
    const PostingList &a, const PostingList &b) {
    PostingList result;
    const auto &left = a.get_all();
    const auto &right = b.get_all();
    size_t i = 0, j = 0;
    while (i < left.size() && j < right.size()) {
        if (left[i].docId == right[j].docId) {
            append_posting(result, left[i]);
            ++i;
            ++j;
        } else if (left[i].docId < right[j].docId) {
            const int target = right[j].docId;
            size_t low = i + 1;
            size_t high = low;
            size_t jump = 1;
            while (high < left.size() && left[high].docId < target) {
                low = high + 1;
                if (jump > left.size() / 2) {
                    high = left.size();
                    break;
                }
                jump *= 2;
                high = i + jump;
            }
            high = high < left.size() ? high + 1 : left.size();
            i = static_cast<size_t>(std::lower_bound(
                left.begin() + static_cast<std::ptrdiff_t>(std::min(low, left.size())),
                left.begin() + static_cast<std::ptrdiff_t>(high), target,
                [](const Posting &posting, int id) { return posting.docId < id; }) - left.begin());
        } else {
            const int target = left[i].docId;
            size_t low = j + 1;
            size_t high = low;
            size_t jump = 1;
            while (high < right.size() && right[high].docId < target) {
                low = high + 1;
                if (jump > right.size() / 2) {
                    high = right.size();
                    break;
                }
                jump *= 2;
                high = j + jump;
            }
            high = high < right.size() ? high + 1 : right.size();
            j = static_cast<size_t>(std::lower_bound(
                right.begin() + static_cast<std::ptrdiff_t>(std::min(low, right.size())),
                right.begin() + static_cast<std::ptrdiff_t>(high), target,
                [](const Posting &posting, int id) { return posting.docId < id; }) - right.begin());
        }
    }
    return result;
}
