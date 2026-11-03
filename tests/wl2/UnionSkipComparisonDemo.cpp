#include "../../wl2/boolean_operations/PostingsOperations.h"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

PostingList make_list(const std::vector<int> &ids) {
    PostingList list;
    list.reserve(ids.size());
    for (int id : ids) {
        Posting posting;
        posting.docId = id;
        posting.positions.push_back(0);
        posting.frequency = 1;
        list.appendSortedPosting(posting);
    }
    return list;
}

double time_union(const PostingList &a, const PostingList &b, bool with_skips) {
    constexpr int iterations = 10;
    volatile std::size_t checksum = 0;
    const auto start = Clock::now();
    for (int i = 0; i < iterations; ++i) {
        PostingList result = with_skips
            ? PostingsOperations::union_with_skips(a, b)
            : PostingsOperations::union_(a, b);
        checksum += result.get_all().size();
    }
    (void)checksum;
    return std::chrono::duration<double, std::micro>(Clock::now() - start).count() / iterations;
}

std::vector<int> extract_ids(const PostingList &list) {
    return PostingsOperations::extract_doc_ids(list);
}

void compare(const char *name, const PostingList &a, const PostingList &b) {
    const PostingList expected = PostingsOperations::union_(a, b);
    const PostingList actual = PostingsOperations::union_with_skips(a, b);
    if (extract_ids(actual) != extract_ids(expected)) {
        std::cerr << "MISMATCH in " << name << '\n';
        std::exit(EXIT_FAILURE);
    }

    // Alternate which function runs first to reduce ordering bias.
    std::vector<double> plain, skips;
    for (int sample = 0; sample < 5; ++sample) {
        if (sample % 2 == 0) {
            plain.push_back(time_union(a, b, false));
            skips.push_back(time_union(a, b, true));
        } else {
            skips.push_back(time_union(a, b, true));
            plain.push_back(time_union(a, b, false));
        }
    }
    std::sort(plain.begin(), plain.end());
    std::sort(skips.begin(), skips.end());
    const double plain_us = plain[plain.size() / 2];
    const double skips_us = skips[skips.size() / 2];
    std::cout << name << " (A=" << a.get_all().size()
              << ", B=" << b.get_all().size()
              << ", union=" << expected.get_all().size()
              << ", outputs identical)\n"
              << std::fixed << std::setprecision(2)
              << "  PostingsOperations::union_:             " << plain_us << " us\n"
              << "  PostingsOperations::union_with_skips:   " << skips_us << " us\n"
              << "  speed ratio (plain / skips):             " << plain_us / skips_us << "x\n\n";
}

} // namespace

int main() {
    std::vector<int> huge, tiny, c1, c2, dense_a, dense_b;
    constexpr int huge_size =
#ifdef SMALL_BENCHMARK
        20000;
#else
        200000;
#endif
    constexpr int tiny_size = 10;
    constexpr int cluster_count =
#ifdef SMALL_BENCHMARK
        10;
#else
        50;
#endif
    constexpr int run_size =
#ifdef SMALL_BENCHMARK
        200;
#else
        2000;
#endif
    for (int i = 0; i < huge_size; ++i) huge.push_back(i);
    for (int i = 0; i < tiny_size; ++i) tiny.push_back(i * (huge_size / tiny_size));
    for (int c = 0; c < cluster_count; ++c)
        for (int k = 0; k < run_size; ++k) {
            c1.push_back(c * run_size * 2 + k);
            c2.push_back(c * run_size * 2 + run_size + k);
        }
    for (int i = 0; i < huge_size / 2; ++i) {
        if (i % 2 == 0) dense_a.push_back(i);
        else dense_b.push_back(i);
    }

    compare("Tiny list vs huge list", make_list(huge), make_list(tiny));
    compare("Clustered runs, no overlap", make_list(c1), make_list(c2));
    compare("Interleaved (worst case for skips)", make_list(dense_a), make_list(dense_b));
}
