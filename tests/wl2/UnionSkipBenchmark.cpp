#include "../../wl2/boolean_operations/PostingsOperations.h"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <random>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
constexpr int iterations = 200;

PostingList make_list(const std::vector<int> &ids) {
    PostingList result;
    for (int id : ids)
        result.addOccurrence(id, 0);
    return result;
}

template <typename Operation>
double time_operation(Operation operation, std::uint64_t &checksum) {
    for (int i = 0; i < 10; ++i)
        checksum += operation().get_all().size();

    const auto start = Clock::now();
    for (int i = 0; i < iterations; ++i)
        checksum += operation().get_all().size();
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
        Clock::now() - start);
    return static_cast<double>(elapsed.count()) / iterations;
}

void benchmark_case(const char *name, const PostingList &a, const PostingList &b) {
    const auto expected = PostingsOperations::extract_doc_ids(
        PostingsOperations::union_(a, b));
    const auto actual = PostingsOperations::extract_doc_ids(
        PostingsOperations::union_with_skips(a, b));
    if (actual != expected) {
        std::cerr << "Correctness check failed for " << name << '\n';
        std::exit(EXIT_FAILURE);
    }

    std::uint64_t checksum = 0;
    const double ordinary_us = time_operation(
        [&] { return PostingsOperations::union_(a, b); }, checksum);
    const double skip_us = time_operation(
        [&] { return PostingsOperations::union_with_skips(a, b); }, checksum);

    std::cout << name << ": A=" << a.get_all().size()
              << ", B=" << b.get_all().size()
              << ", union=" << expected.size() << '\n'
              << "  union_ (no skips):       " << ordinary_us << " us/op\n"
              << "  union_with_skips:        " << skip_us << " us/op\n"
              << "  checksum: " << checksum << '\n';
}

std::vector<int> every_nth(int count, int step) {
    std::vector<int> ids;
    for (int i = 0; i < count; ++i) ids.push_back(i * step);
    return ids;
}

// Clustered: runs of `run` consecutive IDs, then a gap of `gap` (long runs with no
// counterpart in the other list are exactly what skip pointers copy in bulk).
std::vector<int> clustered(int clusters, int run, int gap, int offset) {
    std::vector<int> ids;
    for (int c = 0; c < clusters; ++c)
        for (int k = 0; k < run; ++k) ids.push_back(offset + c * (run + gap) + k);
    return ids;
}

} // namespace

int main() {
    std::mt19937 rng(1729);
    std::bernoulli_distribution include(0.08);
    std::vector<int> left_ids, right_ids;
    for (int id = 0; id < 100000; ++id) {
        if (include(rng)) left_ids.push_back(id);
        if (include(rng)) right_ids.push_back(id);
    }

    benchmark_case("Random sparse lists", make_list(left_ids), make_list(right_ids));
    benchmark_case("Same list", make_list(left_ids), make_list(left_ids));
    // Cases where skip pointers are expected to help: long runs in one list that the
    // other list never touches, or a tiny list against a huge one.
    benchmark_case("Tiny list vs huge list (10 vs 200000)",
                   make_list(every_nth(200000, 1)), make_list(every_nth(10, 20000)));
    benchmark_case("Clustered, non-overlapping runs (runs of 2000)",
                   make_list(clustered(50, 2000, 2000, 0)),
                   make_list(clustered(50, 2000, 2000, 2000)));
    benchmark_case("Empty right list", make_list(left_ids), PostingList{});
}
