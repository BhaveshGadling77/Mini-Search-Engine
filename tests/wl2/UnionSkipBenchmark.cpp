#include "../../wl2/boolean_operations/PostingsOperations.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <random>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
constexpr int SAMPLES = 7;
constexpr int ITERATIONS = 100;

PostingList make_list(const std::vector<int> &ids) {
    PostingList result;
    result.reserve(ids.size());
    for (int id : ids) {
        Posting posting;
        posting.docId = id;
        posting.positions.push_back(0);
        posting.frequency = 1;
        result.appendSortedPosting(posting);
    }
    return result;
}

template <typename Operation>
double time_operation(Operation operation, std::uint64_t &checksum) {
    // 10 warmup iterations
    for (int i = 0; i < 10; ++i)
        checksum += operation().get_all().size();

    const auto start = Clock::now();
    for (int i = 0; i < ITERATIONS; ++i)
        checksum += operation().get_all().size();
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now() - start);
    // return average microseconds per operation
    return (static_cast<double>(elapsed.count()) / 1000.0) / ITERATIONS;
}

double compute_median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

void benchmark_case(const char *name, const char *purpose,
                    const PostingList &a, const PostingList &b) {
    // Correctness check outside of the timed section
    const auto expected = PostingsOperations::extract_doc_ids(
        PostingsOperations::union_(a, b));
    const auto actual = PostingsOperations::extract_doc_ids(
        PostingsOperations::union_with_skips(a, b));
    if (actual != expected) {
        std::cerr << "Correctness check failed for " << name << '\n';
        std::exit(EXIT_FAILURE);
    }

    std::uint64_t checksum = 0;
    std::vector<double> ordinary_samples(SAMPLES);
    std::vector<double> skip_samples(SAMPLES);

    // Run 7 independent timed samples, alternating which implementation runs first
    for (int s = 0; s < SAMPLES; ++s) {
        if (s % 2 == 0) {
            ordinary_samples[s] = time_operation(
                [&] { return PostingsOperations::union_(a, b); }, checksum);
            skip_samples[s] = time_operation(
                [&] { return PostingsOperations::union_with_skips(a, b); }, checksum);
        } else {
            skip_samples[s] = time_operation(
                [&] { return PostingsOperations::union_with_skips(a, b); }, checksum);
            ordinary_samples[s] = time_operation(
                [&] { return PostingsOperations::union_(a, b); }, checksum);
        }
    }

    const double median_ordinary = compute_median(ordinary_samples);
    const double median_skip = compute_median(skip_samples);
    const double speedup = median_ordinary / median_skip;

    std::cout << "=================================================================\n";
    std::cout << "Test:    " << name << "\n";
    std::cout << "Purpose: " << purpose << "\n";
    std::cout << "Sizes:   |A| = " << a.get_all().size()
              << ", |B| = " << b.get_all().size()
              << ", |A U B| = " << expected.size() << "\n";
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "  union_ (ordinary baseline): " << std::setw(9) << median_ordinary << " us/op (median of " << SAMPLES << " runs)\n";
    std::cout << "  union_with_skips:           " << std::setw(9) << median_skip << " us/op (median of " << SAMPLES << " runs)\n";
    std::cout << "  Speedup (T_ordinary / T_skip): " << std::setprecision(4) << speedup << "x";
    if (speedup > 1.05) {
        std::cout << "  --> Skip implementation is FASTER\n";
    } else if (speedup < 0.95) {
        std::cout << "  --> Skip implementation is SLOWER\n";
    } else {
        std::cout << "  --> Similar performance (~equal)\n";
    }
}

std::vector<int> every_nth(int count, int step) {
    std::vector<int> ids;
    ids.reserve(count);
    for (int i = 0; i < count; ++i) ids.push_back(i * step);
    return ids;
}

std::vector<int> clustered(int clusters, int run, int gap, int offset) {
    std::vector<int> ids;
    ids.reserve(clusters * run);
    for (int c = 0; c < clusters; ++c)
        for (int k = 0; k < run; ++k) ids.push_back(offset + c * (run + gap) + k);
    return ids;
}

} // namespace

int main() {
    std::cout << "Running Union vs Skip-Union Benchmark (C++17 -O2, "
              << SAMPLES << " samples x " << ITERATIONS << " iterations)\n\n";

    std::mt19937 rng(1729);
    std::bernoulli_distribution include(0.08);
    std::vector<int> left_ids, right_ids;
    for (int id = 0; id < 100000; ++id) {
        if (include(rng)) left_ids.push_back(id);
        if (include(rng)) right_ids.push_back(id);
    }

    const PostingList list_left = make_list(left_ids);
    const PostingList list_right = make_list(right_ids);

    // 1. Random sparse lists (General performance)
    benchmark_case("Random sparse lists", "General performance",
                   list_left, list_right);

    // 2. Identical lists (High overlap)
    benchmark_case("Identical lists", "High overlap",
                   list_left, list_left);

    // 3. Disjoint lists (No overlap)
    std::vector<int> disjoint_left, disjoint_right;
    for (int id = 0; id < 100000; ++id) {
        if (id < 50000) disjoint_left.push_back(id * 2);
        else disjoint_right.push_back(id * 2 + 1);
    }
    benchmark_case("Disjoint lists", "No overlap",
                   make_list(disjoint_left), make_list(disjoint_right));

    // 4. Tiny vs huge (Highly unequal sizes)
    benchmark_case("Tiny vs huge lists", "Highly unequal sizes",
                   make_list(every_nth(200000, 1)), make_list(every_nth(10, 20000)));

    // 5. Clustered runs (Long stretches suitable for skipping)
    benchmark_case("Clustered runs", "Long stretches suitable for skipping",
                   make_list(clustered(50, 2000, 2000, 0)),
                   make_list(clustered(50, 2000, 2000, 2000)));

    // 6. Interleaved lists (Skip pointers should not help)
    std::vector<int> interleaved_left, interleaved_right;
    for (int id = 0; id < 100000; ++id) {
        if (id % 2 == 0) interleaved_left.push_back(id);
        else interleaved_right.push_back(id);
    }
    benchmark_case("Interleaved lists", "Dense alternating IDs; baseline fallback",
                   make_list(interleaved_left), make_list(interleaved_right));

    // 7. Empty list (Boundary case)
    benchmark_case("Empty list", "Boundary case",
                   list_left, PostingList{});

    std::cout << "=================================================================\n";
    std::cout << "Benchmark complete.\n";
    return 0;
}
