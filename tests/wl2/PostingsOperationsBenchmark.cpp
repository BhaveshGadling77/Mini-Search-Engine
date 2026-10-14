#include "../../wl2/boolean_operations/PostingsOperations.h"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
constexpr int list_size = 1000;
constexpr int iterations = 20;

PostingList make_posting_list(const std::vector<int>& doc_ids) {
    PostingList list;
    for (int doc_id : doc_ids) list.addOccurrence(doc_id, 0);
    return list;
}

template <typename Operation>
double average_microseconds(Operation operation, std::uint64_t& checksum) {
    const auto start = Clock::now();
    for (int i = 0; i < iterations; ++i) {
        const PostingList result = operation();
        checksum += result.get_all().size();
        if (!result.get_all().empty()) checksum += static_cast<std::uint64_t>(result.get_all().front().docId);
    }
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - start);
    return static_cast<double>(elapsed.count()) / iterations;
}

void benchmark_case(const std::string& name, const PostingList& a, const PostingList& b) {
    const std::vector<int> normal_result =
        PostingsOperations::extract_doc_ids(PostingsOperations::intersect(a, b));
    const std::vector<int> skip_result =
        PostingsOperations::extract_doc_ids(PostingsOperations::intersect_with_skips(a, b));
    if (normal_result != skip_result) {
        std::cerr << "Intersection results differ for benchmark case: " << name << '\n';
        std::exit(1);
    }

    std::uint64_t checksum = 0;
    // Warm up both paths before measuring.
    checksum += PostingsOperations::intersect(a, b).get_all().size();
    checksum += PostingsOperations::intersect_with_skips(a, b).get_all().size();

    const double normal_us = average_microseconds(
        [&] { return PostingsOperations::intersect(a, b); }, checksum);
    const double skip_us = average_microseconds(
        [&] { return PostingsOperations::intersect_with_skips(a, b); }, checksum);

    std::cout << name << " (A=" << a.get_all().size() << ", B=" << b.get_all().size()
              << ", matches=" << normal_result.size() << ")\n"
              << "  without skip pointers: " << normal_us << " us/op\n"
              << "  with skip pointers:    " << skip_us << " us/op\n"
              << "  without/with ratio: " << (skip_us == 0.0 ? 0.0 : normal_us / skip_us)
              << "x\n";
    // Keep benchmark results observable to the compiler and make checksum reproducible.
    std::cout << "  checksum: " << checksum << '\n';
}

} // namespace

int main() {
    std::vector<int> dense_a;
    std::vector<int> dense_b;
    std::vector<int> disjoint_a;
    std::vector<int> disjoint_b;
    std::vector<int> sparse_a;
    std::vector<int> sparse_b;

    dense_a.reserve(list_size);
    dense_b.reserve(list_size);
    disjoint_a.reserve(list_size);
    disjoint_b.reserve(list_size);
    sparse_a.reserve(list_size);
    sparse_b.reserve(list_size / 100);

    for (int i = 0; i < list_size; ++i) {
        dense_a.push_back(i);
        dense_b.push_back(i);
        disjoint_a.push_back(i * 2);
        disjoint_b.push_back(i * 2 + 1);
        sparse_a.push_back(i * 2);
        if (i % 100 == 0) sparse_b.push_back(i * 2);
    }

    const PostingList dense_left = make_posting_list(dense_a);
    const PostingList dense_right = make_posting_list(dense_b);
    const PostingList disjoint_left = make_posting_list(disjoint_a);
    const PostingList disjoint_right = make_posting_list(disjoint_b);
    const PostingList sparse_left = make_posting_list(sparse_a);
    const PostingList sparse_right = make_posting_list(sparse_b);

    std::cout << "Intersection benchmark, " << iterations << " iterations per method\n";
    benchmark_case("dense overlap", dense_left, dense_right);
    benchmark_case("disjoint, interleaved IDs", disjoint_left, disjoint_right);
    benchmark_case("sparse right list", sparse_left, sparse_right);
    return 0;
}
