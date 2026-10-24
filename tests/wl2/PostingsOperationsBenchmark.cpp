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

// Fixed skip intervals to compare.
constexpr int fixed_intervals[] = {10, 25, 50, 100};

PostingList make_posting_list(const std::vector<int>& doc_ids) {
    PostingList list;

    for (int doc_id : doc_ids) {
        list.addOccurrence(doc_id, 0);
    }

    return list;
}

template <typename Operation>
double average_microseconds(
    Operation operation,
    std::uint64_t& checksum
) {
    const auto start = Clock::now();

    for (int i = 0; i < iterations; ++i) {
        const PostingList result = operation();
        const auto postings = result.get_all();

        checksum += postings.size();

        if (!postings.empty()) {
            checksum += static_cast<std::uint64_t>(
                postings.front().docId
            );
        }
    }

    const auto elapsed =
        std::chrono::duration_cast<std::chrono::microseconds>(
            Clock::now() - start
        );

    return static_cast<double>(elapsed.count()) / iterations;
}

template <typename Operation>
void benchmark_strategy(
    const std::string& name,
    Operation operation,
    const std::vector<int>& expected,
    std::uint64_t& checksum
) {
    // Validate correctness before timing.
    const PostingList result = operation();

    const std::vector<int> actual =
        PostingsOperations::extract_doc_ids(result);

    if (actual != expected) {
        std::cerr << "ERROR: Incorrect results for "
                  << name << '\n';

        std::exit(1);
    }

    // Warm-up.
    for (int i = 0; i < 3; ++i) {
        const PostingList warmup = operation();
        checksum += warmup.get_all().size();
    }

    const double time_us =
        average_microseconds(operation, checksum);

    std::cout << "  " << name << ": "
              << time_us << " us/op\n";
}

void benchmark_case(
    const std::string& name,
    const PostingList& a,
    const PostingList& b
) {
    const std::vector<int> expected =
        PostingsOperations::extract_doc_ids(
            PostingsOperations::intersect(a, b)
        );

    std::uint64_t checksum = 0;

    std::cout << "\n\n";
    std::cout << "Case: " << name << '\n';
    std::cout << "A size: " << a.get_all().size() << '\n';
    std::cout << "B size: " << b.get_all().size() << '\n';
    std::cout << "Matches: " << expected.size() << '\n';
    std::cout << "\n";

    benchmark_strategy(
        "Standard intersection",
        [&]() {
            return PostingsOperations::intersect(a, b);
        },
        expected,
        checksum
    );

    benchmark_strategy(
        "Existing skip pointers",
        [&]() {
            return PostingsOperations::intersect_with_skips(a, b);
        },
        expected,
        checksum
    );

    benchmark_strategy(
        "Square-root skips",
        [&]() {
            return PostingsOperations::intersect_with_sqrt_skips(a, b);
        },
        expected,
        checksum
    );

    for (int interval : fixed_intervals) {
        benchmark_strategy(
            "Fixed interval = " + std::to_string(interval),
            [&]() {
                return PostingsOperations::intersect_with_fixed_skips(
                    a, b, interval
                );
            },
            expected,
            checksum
        );
    }

    benchmark_strategy(
        "Exponential skips",
        [&]() {
            return PostingsOperations::intersect_with_exponential_skips(
                a, b
            );
        },
        expected,
        checksum
    );

   cout << endl;
    std::cout << "Checksum: " << checksum << '\n';
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
        // Both lists contain identical document IDs.
        dense_a.push_back(i);
        dense_b.push_back(i);

        // Interleaved IDs: no intersection.
        disjoint_a.push_back(i * 2);
        disjoint_b.push_back(i * 2 + 1);

        // One list is dense; the other is sparse.
        sparse_a.push_back(i * 2);

        if (i % 100 == 0) {
            sparse_b.push_back(i * 2);
        }
    }

    const PostingList dense_left =
        make_posting_list(dense_a);

    const PostingList dense_right =
        make_posting_list(dense_b);

    const PostingList disjoint_left =
        make_posting_list(disjoint_a);

    const PostingList disjoint_right =
        make_posting_list(disjoint_b);

    const PostingList sparse_left =
        make_posting_list(sparse_a);

    const PostingList sparse_right =
        make_posting_list(sparse_b);

    std::cout
        << "Posting intersection benchmark\n"
        << "Iterations per strategy: " << iterations
        << '\n';

    benchmark_case(
        "Dense overlap",
        dense_left,
        dense_right
    );

    benchmark_case(
        "Disjoint, interleaved IDs",
        disjoint_left,
        disjoint_right
    );

    benchmark_case(
        "Sparse right list",
        sparse_left,
        sparse_right
    );

    return 0;
}