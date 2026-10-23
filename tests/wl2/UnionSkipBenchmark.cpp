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
    benchmark_case("Empty right list", make_list(left_ids), PostingList{});
}
