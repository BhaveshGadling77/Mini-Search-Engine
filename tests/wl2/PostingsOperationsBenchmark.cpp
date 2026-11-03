#include "../../wl2/boolean_operations/PostingsOperations.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <random>
#include <string>
#include <utility>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
using Operation = std::function<PostingList()>;

constexpr int samples = 7;
constexpr int fixed_offsets[] = {3, 10, 25, 31, 50, 100, 141, 223, 316, 447};
volatile std::uint64_t result_sink = 0;

struct Strategy {
    std::string name;
    Operation run;
};

struct Case {
    std::string name;
    std::vector<int> left_ids;
    std::vector<int> right_ids;
};

PostingList make_list(const std::vector<int>& ids) {
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

std::vector<int> sequence(int start, int count, int step = 1) {
    std::vector<int> ids;
    ids.reserve(count);
    for (int i = 0; i < count; ++i)
        ids.push_back(start + i * step);
    return ids;
}

std::vector<int> clustered(int clusters, int run_size, int gap, int offset) {
    std::vector<int> ids;
    ids.reserve(clusters * run_size);
    for (int c = 0; c < clusters; ++c) {
        const int start = offset + c * (run_size * 2 + gap);
        for (int k = 0; k < run_size; ++k)
            ids.push_back(start + k);
    }
    return ids;
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

std::vector<Strategy> make_strategies(const PostingList& a, const PostingList& b) {
    std::vector<Strategy> strategies;
    strategies.push_back({"Plain union", [&] { return PostingsOperations::union_(a, b); }});

    const int sqrt_a = std::max(1, static_cast<int>(std::sqrt(static_cast<double>(a.get_all().size()))));
    const int sqrt_b = std::max(1, static_cast<int>(std::sqrt(static_cast<double>(b.get_all().size()))));
    strategies.push_back({
        "Sqrt skips (A=" + std::to_string(sqrt_a) + ", B=" + std::to_string(sqrt_b) + ")",
        [&] { return PostingsOperations::union_with_skips(a, b); }
    });

    for (int offset : fixed_offsets) {
        strategies.push_back({
            "Fixed " + std::to_string(offset),
            [&, offset] { return PostingsOperations::union_with_fixed_skips(a, b, offset); }
        });
    }
    strategies.push_back({"Exponential", [&] { return PostingsOperations::union_with_exponential_skips(a, b); }});
    return strategies;
}

void benchmark_case(const Case& test_case) {
    const PostingList a = make_list(test_case.left_ids);
    const PostingList b = make_list(test_case.right_ids);
    const std::vector<int> expected = PostingsOperations::extract_doc_ids(
        PostingsOperations::union_(a, b));
    std::vector<Strategy> strategies = make_strategies(a, b);
    std::vector<std::vector<double>> timings(strategies.size());

    // Keep the amount of output copying per timing sample bounded across cases.
    const int output_count = static_cast<int>(
        std::max<std::size_t>(1, expected.size()));
    const int iterations = std::max(3, std::min(30, 500000 / output_count));

    for (std::size_t s = 0; s < strategies.size(); ++s) {
        const std::vector<int> actual = PostingsOperations::extract_doc_ids(strategies[s].run());
        if (actual != expected) {
            std::cerr << "Incorrect output for " << strategies[s].name
                      << " in case " << test_case.name << '\n';
            std::exit(EXIT_FAILURE);
        }
        for (int warmup = 0; warmup < 2; ++warmup)
            result_sink += strategies[s].run().get_all().size();
    }

    // Rotate timing order between samples to reduce systematic order/cache bias.
    for (int sample = 0; sample < samples; ++sample) {
        for (std::size_t step = 0; step < strategies.size(); ++step) {
            const std::size_t index = (step + sample) % strategies.size();
            const auto start = Clock::now();
            for (int i = 0; i < iterations; ++i)
                result_sink += strategies[index].run().get_all().size();
            const auto elapsed = std::chrono::duration<double, std::micro>(Clock::now() - start).count();
            timings[index].push_back(elapsed / iterations);
        }
    }

    std::vector<double> medians;
    medians.reserve(strategies.size());
    for (const auto& values : timings)
        medians.push_back(median(values));
    const double best = *std::min_element(medians.begin(), medians.end());

    std::cout << "\nCase: " << test_case.name << '\n'
              << "A=" << a.get_all().size() << ", B=" << b.get_all().size()
              << ", union=" << expected.size() << ", samples=" << samples
              << ", iterations/sample=" << iterations << '\n';
    for (std::size_t i = 0; i < strategies.size(); ++i) {
        std::cout << "  " << std::left << std::setw(24) << strategies[i].name
                  << std::right << std::fixed << std::setprecision(2)
                  << medians[i] << " us/op  (" << std::setprecision(3)
                  << best / medians[i] << "x of fastest)";
        if (medians[i] == best)
            std::cout << "  <-- fastest measured";
        std::cout << '\n';
    }
}

std::vector<Case> make_cases() {
    std::vector<Case> cases;

    // Existing large union benchmark workloads.
    std::mt19937 rng(1729);
    std::bernoulli_distribution include(0.08);
    std::vector<int> random_a, random_b;
    for (int id = 0; id < 100000; ++id) {
        if (include(rng)) random_a.push_back(id);
        if (include(rng)) random_b.push_back(id);
    }
    cases.push_back({"Random sparse lists", random_a, random_b});
    cases.push_back({"Identical lists / dense overlap", random_a, random_a});

    cases.push_back({"Disjoint separated ranges", sequence(0, 50000), sequence(50000, 50000)});
    cases.push_back({"Tiny versus huge", sequence(0, 200000), sequence(0, 10, 20000)});
    cases.push_back({"Clustered non-overlapping runs",
        clustered(50, 2000, 0, 0), clustered(50, 2000, 0, 2000)});
    // Target the square-root stride model: list length 10,000 (sqrt=100),
    // with alternating 400-document runs that allow several 100-entry jumps.
    cases.push_back({"Sqrt-scale alternating runs (n=10k, block=400)",
        clustered(25, 400, 0, 0), clustered(25, 400, 0, 400)});

    std::vector<int> even_ids, odd_ids;
    for (int id = 0; id < 100000; ++id) {
        if (id % 2 == 0) even_ids.push_back(id);
        else odd_ids.push_back(id);
    }
    cases.push_back({"Interleaved disjoint IDs", even_ids, odd_ids});

    // Existing offset benchmark workloads and additional overlap/skew cases.
    cases.push_back({"Dense partial overlap", sequence(0, 20000), sequence(10000, 20000)});
    cases.push_back({"Sparse right list", sequence(0, 100000, 2), sequence(0, 1000, 200)});
    cases.push_back({"Empty right list", random_a, {}});

    return cases;
}

} // namespace

int main() {
    std::cout << "Union benchmark: plain vs sqrt vs fixed offsets vs exponential\n"
              << "Fixed offsets: ";
    for (std::size_t i = 0; i < std::size(fixed_offsets); ++i)
        std::cout << (i ? ", " : "") << fixed_offsets[i];
    std::cout << "\nEach strategy validates output; timings are medians of "
              << samples << " samples with rotated run order.\n";

    for (const Case& test_case : make_cases())
        benchmark_case(test_case);
    return result_sink == 0 ? EXIT_FAILURE : EXIT_SUCCESS;
}
