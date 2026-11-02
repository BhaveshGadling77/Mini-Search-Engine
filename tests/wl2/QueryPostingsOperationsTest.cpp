#include "../../wl2/boolean_operations/PostingsOperations.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <random>
#include <string>
#include <vector>

namespace {

int failures = 0;

void expect_equal(const std::string &name, const std::vector<int> &actual,
                  const std::vector<int> &expected) {
    if (actual == expected)
        return;
    ++failures;
    std::cerr << "FAIL: " << name << "\n  expected:";
    for (int id : expected)
        std::cerr << ' ' << id;
    std::cerr << "\n  actual:  ";
    for (int id : actual)
        std::cerr << ' ' << id;
    std::cerr << '\n';
}

PostingList make_list(const std::vector<int> &doc_ids) {
    PostingList list;
    for (int id : doc_ids)
        list.addOccurrence(id, 0);
    return list;
}

std::vector<int> expected_intersection(const std::vector<int> &a, const std::vector<int> &b) {
    std::vector<int> result;
    std::set_intersection(a.begin(), a.end(), b.begin(), b.end(), std::back_inserter(result));
    return result;
}

std::vector<int> expected_union(const std::vector<int> &a, const std::vector<int> &b) {
    std::vector<int> result;
    std::set_union(a.begin(), a.end(), b.begin(), b.end(), std::back_inserter(result));
    return result;
}

std::vector<int> expected_difference(const std::vector<int> &a, const std::vector<int> &b) {
    std::vector<int> result;
    std::set_difference(a.begin(), a.end(), b.begin(), b.end(), std::back_inserter(result));
    return result;
}

void test_basic_operations() {
    const PostingList a = make_list({1, 2, 4, 7});
    const PostingList b = make_list({2, 4, 5, 7});

    expect_equal("AND", PostingsOperations::extract_doc_ids(PostingsOperations::intersect(a, b)),
                 {2, 4, 7});
    expect_equal("OR", PostingsOperations::extract_doc_ids(PostingsOperations::union_(a, b)),
                 {1, 2, 4, 5, 7});
    expect_equal("skip OR",
                 PostingsOperations::extract_doc_ids(PostingsOperations::union_with_skips(a, b)),
                 {1, 2, 4, 5, 7});
    expect_equal("NOT A minus B",
                 PostingsOperations::extract_doc_ids(PostingsOperations::difference(a, b)), {1});
    expect_equal(
        "legacy skip-named OR",
        PostingsOperations::extract_doc_ids(PostingsOperations::intersect_with_skips(a, b)),
        {1, 2, 4, 5, 7});
    expect_equal("sqrt skip-named OR",
                 PostingsOperations::extract_doc_ids(
                     PostingsOperations::intersect_with_sqrt_skips(a, b)),
                 {1, 2, 4, 5, 7});
    expect_equal("fixed skip-named OR",
                 PostingsOperations::extract_doc_ids(
                     PostingsOperations::intersect_with_fixed_skips(a, b, 3)),
                 {1, 2, 4, 5, 7});
    expect_equal("exponential skip-named OR",
                 PostingsOperations::extract_doc_ids(
                     PostingsOperations::intersect_with_exponential_skips(a, b)),
                 {1, 2, 4, 5, 7});
}

void test_empty_and_boundary_lists() {
    const PostingList empty;
    const PostingList values = make_list({3, 8, 13});

    expect_equal("empty AND",
                 PostingsOperations::extract_doc_ids(PostingsOperations::intersect(empty, values)),
                 {});
    expect_equal("empty OR",
                 PostingsOperations::extract_doc_ids(PostingsOperations::union_(empty, values)),
                 {3, 8, 13});
    expect_equal("empty skip OR",
                 PostingsOperations::extract_doc_ids(PostingsOperations::union_with_skips(empty, values)),
                 {3, 8, 13});
    expect_equal("skip OR empty",
                 PostingsOperations::extract_doc_ids(PostingsOperations::union_with_skips(values, empty)),
                 {3, 8, 13});
    expect_equal("empty NOT",
                 PostingsOperations::extract_doc_ids(PostingsOperations::difference(empty, values)),
                 {});
    expect_equal("values NOT empty",
                 PostingsOperations::extract_doc_ids(PostingsOperations::difference(values, empty)),
                 {3, 8, 13});
    expect_equal(
        "identical lists NOT",
        PostingsOperations::extract_doc_ids(PostingsOperations::difference(values, values)), {});
}

void test_posting_data_is_preserved() {
    PostingList a;
    a.addOccurrence(10, 2);
    a.addOccurrence(10, 5);
    a.addOccurrence(20, 1);
    PostingList b = make_list({10, 30});

    const PostingList result = PostingsOperations::intersect(a, b);
    expect_equal("intersection keeps matching document",
                 PostingsOperations::extract_doc_ids(result), {10});
    if (result.get_all().size() != 1 || result.get_all()[0].positions != std::vector<int>({2, 5})) {
        ++failures;
        std::cerr << "FAIL: intersection should preserve the left posting's positions\n";
    }
}

void test_many_sorted_inputs() {
    std::mt19937 generator(1729);
    std::uniform_int_distribution<int> include_doc(0, 1);

    for (int trial = 0; trial < 250; ++trial) {
        std::vector<int> ids_a;
        std::vector<int> ids_b;
        for (int doc_id = 0; doc_id < 200; ++doc_id) {
            if (include_doc(generator))
                ids_a.push_back(doc_id);
            if (include_doc(generator))
                ids_b.push_back(doc_id);
        }

        const PostingList a = make_list(ids_a);
        const PostingList b = make_list(ids_b);
        const std::string label = "generated trial " + std::to_string(trial);

        expect_equal(label + " AND",
                     PostingsOperations::extract_doc_ids(PostingsOperations::intersect(a, b)),
                     expected_intersection(ids_a, ids_b));
        expect_equal(label + " OR",
                     PostingsOperations::extract_doc_ids(PostingsOperations::union_(a, b)),
                     expected_union(ids_a, ids_b));
        expect_equal(label + " skip OR",
                     PostingsOperations::extract_doc_ids(PostingsOperations::union_with_skips(a, b)),
                     expected_union(ids_a, ids_b));
        expect_equal(label + " NOT",
                     PostingsOperations::extract_doc_ids(PostingsOperations::difference(a, b)),
                     expected_difference(ids_a, ids_b));
    expect_equal(
        label + " legacy skip-named OR",
            PostingsOperations::extract_doc_ids(PostingsOperations::intersect_with_skips(a, b)),
        expected_union(ids_a, ids_b));
        expect_equal(label + " sqrt skip-named OR",
                     PostingsOperations::extract_doc_ids(
                         PostingsOperations::intersect_with_sqrt_skips(a, b)),
                     expected_union(ids_a, ids_b));
        expect_equal(label + " fixed skip-named OR",
                     PostingsOperations::extract_doc_ids(
                         PostingsOperations::intersect_with_fixed_skips(a, b, 7)),
                     expected_union(ids_a, ids_b));
        expect_equal(label + " exponential skip-named OR",
                     PostingsOperations::extract_doc_ids(
                         PostingsOperations::intersect_with_exponential_skips(a, b)),
                     expected_union(ids_a, ids_b));
    }
}

bool same_postings(const PostingList &x, const PostingList &y) {
    const auto &p = x.get_all();
    const auto &q = y.get_all();
    if (p.size() != q.size()) return false;
    for (size_t k = 0; k < p.size(); ++k)
        if (p[k].docId != q[k].docId || p[k].frequency != q[k].frequency ||
            p[k].positions != q[k].positions)
            return false;
    return true;
}

// Every skip-pointer union must equal union_() posting-for-posting (IDs, frequencies,
// positions), across list sizes/densities that exercise long skips, short skips,
// no overlap, full overlap, and very unequal lengths.
void test_skip_union_equals_normal_union() {
    std::mt19937 gen(4242);
    const int universes[] = {1, 5, 50, 400, 3000};
    const double densities[] = {0.02, 0.1, 0.5, 0.95};
    int trial = 0;
    for (int universe : universes)
        for (double da : densities)
            for (double db : densities)
                for (int rep = 0; rep < 6; ++rep, ++trial) {
                    std::bernoulli_distribution ia(da), ib(db);
                    PostingList a, b;
                    for (int id = 0; id < universe; ++id) {
                        if (ia(gen)) { a.addOccurrence(id, id % 7); a.addOccurrence(id, 9); }
                        if (ib(gen)) b.addOccurrence(id, id % 3);
                    }
                    const PostingList expected = PostingsOperations::union_(a, b);
                    const std::string label = "skip-equivalence trial " + std::to_string(trial);
                    auto check = [&](const char *name, const PostingList &got) {
                        if (!same_postings(got, expected)) {
                            ++failures;
                            std::cerr << "FAIL: " << label << " " << name << " differs from union_\n";
                        }
                    };
                    check("union_with_skips", PostingsOperations::union_with_skips(a, b));
                    for (int k : {-3, 0, 1, 2, 3, 7, 64})
                        check("fixed", PostingsOperations::union_with_fixed_skips(a, b, k));
                    check("exponential", PostingsOperations::union_with_exponential_skips(a, b));
                    check("legacy intersect_with_skips", PostingsOperations::intersect_with_skips(a, b));
                    // Output must be strictly increasing (sorted, no duplicates).
                    const auto ids = PostingsOperations::extract_doc_ids(
                        PostingsOperations::union_with_skips(a, b));
                    if (!std::is_sorted(ids.begin(), ids.end()) ||
                        std::adjacent_find(ids.begin(), ids.end()) != ids.end()) {
                        ++failures;
                        std::cerr << "FAIL: " << label << " output not strictly sorted\n";
                    }
                }

    // Skewed: one huge list, one tiny list, with the tiny one's ids at the extremes.
    std::vector<int> big;
    for (int id = 0; id < 10000; id += 2) big.push_back(id);
    for (const std::vector<int> &small : {std::vector<int>{}, {0}, {9998}, {1, 9999, 20000}, {-5, 4, 5}}) {
        const PostingList A = make_list(big), B = make_list(small);
        for (int order = 0; order < 2; ++order) {
            const PostingList &x = order ? B : A, &y = order ? A : B;
            if (!same_postings(PostingsOperations::union_with_skips(x, y), PostingsOperations::union_(x, y)) ||
                !same_postings(PostingsOperations::union_with_exponential_skips(x, y),
                               PostingsOperations::union_(x, y))) {
                ++failures;
                std::cerr << "FAIL: skewed skip union differs from union_\n";
            }
        }
    }
}

} // namespace

int main() {
    test_basic_operations();
    test_empty_and_boundary_lists();
    test_posting_data_is_preserved();
    test_many_sorted_inputs();
    test_skip_union_equals_normal_union();

    if (failures != 0) {
        std::cerr << failures << " test(s) failed.\n";
        return EXIT_FAILURE;
    }
    std::cout << "All PostingList Boolean operation tests passed.\n";
    return EXIT_SUCCESS;
}
