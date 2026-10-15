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

    expect_equal("AND", PostingsOperations::extract_doc_ids(PostingsOperations::boolean_and(a, b)),
                 {2, 4, 7});
    expect_equal("OR", PostingsOperations::extract_doc_ids(PostingsOperations::boolean_or(a, b)),
                 {1, 2, 4, 5, 7});
    expect_equal("NOT A minus B",
                 PostingsOperations::extract_doc_ids(PostingsOperations::boolean_not(a, b)), {1});
    expect_equal(
        "skip AND",
        PostingsOperations::extract_doc_ids(PostingsOperations::intersect_with_skips(a, b)),
        {2, 4, 7});
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
        expect_equal(label + " NOT",
                     PostingsOperations::extract_doc_ids(PostingsOperations::difference(a, b)),
                     expected_difference(ids_a, ids_b));
        expect_equal(
            label + " skip AND",
            PostingsOperations::extract_doc_ids(PostingsOperations::intersect_with_skips(a, b)),
            expected_intersection(ids_a, ids_b));
    }
}

} // namespace

int main() {
    test_basic_operations();
    test_empty_and_boundary_lists();
    test_posting_data_is_preserved();
    test_many_sorted_inputs();

    if (failures != 0) {
        std::cerr << failures << " test(s) failed.\n";
        return EXIT_FAILURE;
    }
    std::cout << "All PostingList Boolean operation tests passed.\n";
    return EXIT_SUCCESS;
}
