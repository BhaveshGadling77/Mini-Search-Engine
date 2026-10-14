#include <iostream>
#include <vector>
#include <string>
#include <cassert>
#include <sstream>
#include <chrono>
#include <random>
#include <algorithm>
#include "../../wl2/boolean_operations/PostingsOperations.h"

using namespace std;

// Simple test framework
static int g_passCount = 0;
static int g_failCount = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            cerr << "  [FAIL] " << msg << " (line " << __LINE__ << ")" << endl; \
            g_failCount++; \
            return; \
        } \
    } while (0)

#define RUN_TEST(fn) \
    do { \
        cout << "[RUN] " << #fn << "..." << endl; \
        int beforeFail = g_failCount; \
        fn(); \
        if (g_failCount == beforeFail) { \
            cout << "  [PASS] " << #fn << endl; \
            g_passCount++; \
        } \
    } while (0)

// Helper: create a sorted PostingList from a vector of ascending docIds
static PostingList makeList(const vector<int>& docIds) {
    PostingList list;
    for (int id : docIds) {
        list.add(Posting(id, 1, {0}));
    }
    return list;
}

// Helper: create a PostingList from a vector of Posting objects (must be sorted by docId)
static PostingList makeListFromPostings(const vector<Posting>& postings) {
    PostingList list;
    for (const auto& p : postings) {
        list.add(p);
    }
    return list;
}

static vector<int> getDocIds(const PostingList& list) {
    return PostingsOperations::extract_doc_ids(list);
}

static bool checkDocIds(const PostingList& list, const vector<int>& expected) {
    vector<int> actual = getDocIds(list);
    return actual == expected;
}

// Baseline Example
void test_baseline_example() {
    // A = [1, 2, 4, 7], B = [2, 4, 5, 7]
    // AND = [2, 4, 7], OR = [1, 2, 4, 5, 7], NOT = [1]
    PostingList a = makeList({1, 2, 4, 7});
    PostingList b = makeList({2, 4, 5, 7});

    TEST_ASSERT(checkDocIds(PostingsOperations::intersect(a, b), {2, 4, 7}), "Baseline AND failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {1, 2, 4, 5, 7}), "Baseline OR failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, b), {1}), "Baseline NOT failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect_with_skips(a, b), {2, 4, 7}), "Baseline skip AND failed");
}

// Test 1: Both lists empty
void test_1_both_lists_empty() {
    PostingList a;
    PostingList b;

    TEST_ASSERT(PostingsOperations::intersect(a, b).empty(), "AND of empty lists should be empty");
    TEST_ASSERT(PostingsOperations::union_(a, b).empty(), "OR of empty lists should be empty");
    TEST_ASSERT(PostingsOperations::difference(a, b).empty(), "NOT of empty lists should be empty");
    TEST_ASSERT(PostingsOperations::intersect_with_skips(a, b).empty(), "Skip AND of empty lists should be empty");
}

// Test 2: First list empty
void test_2_first_list_empty() {
    PostingList a;
    PostingList b = makeList({1, 3, 5});

    TEST_ASSERT(PostingsOperations::intersect(a, b).empty(), "AND with empty left should be empty");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {1, 3, 5}), "OR with empty left should equal right");
    TEST_ASSERT(PostingsOperations::difference(a, b).empty(), "NOT with empty left should be empty");
    TEST_ASSERT(PostingsOperations::intersect_with_skips(a, b).empty(), "Skip AND with empty left should be empty");
}

// Test 3: Second list empty
void test_3_second_list_empty() {
    PostingList a = makeList({2, 4, 6});
    PostingList b;

    TEST_ASSERT(PostingsOperations::intersect(a, b).empty(), "AND with empty right should be empty");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {2, 4, 6}), "OR with empty right should equal left");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, b), {2, 4, 6}), "NOT with empty right should equal left");
    TEST_ASSERT(PostingsOperations::intersect_with_skips(a, b).empty(), "Skip AND with empty right should be empty");
}

// Test 4: Disjoint lists
void test_4_disjoint_lists() {
    PostingList a = makeList({1, 3, 5, 7});
    PostingList b = makeList({2, 4, 6, 8});

    TEST_ASSERT(PostingsOperations::intersect(a, b).empty(), "AND of disjoint lists should be empty");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {1, 2, 3, 4, 5, 6, 7, 8}), "OR of disjoint lists failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, b), {1, 3, 5, 7}), "NOT of disjoint lists should equal left");
    TEST_ASSERT(PostingsOperations::intersect_with_skips(a, b).empty(), "Skip AND of disjoint lists should be empty");
}


// Test 5: Identical lists

void test_5_identical_lists() {
    PostingList a = makeList({10, 20, 30});
    PostingList b = makeList({10, 20, 30});

    TEST_ASSERT(checkDocIds(PostingsOperations::intersect(a, b), {10, 20, 30}), "AND of identical lists failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {10, 20, 30}), "OR of identical lists failed");
    TEST_ASSERT(PostingsOperations::difference(a, b).empty(), "NOT of identical lists should be empty");
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect_with_skips(a, b), {10, 20, 30}), "Skip AND of identical lists failed");
}


// Test 6: Subset relationships

void test_6_subset_relationships() {
    PostingList a = makeList({1, 2, 3, 4, 5, 6});
    PostingList b = makeList({2, 4, 6});

    TEST_ASSERT(checkDocIds(PostingsOperations::intersect(a, b), {2, 4, 6}), "A AND B (B subset) should equal B");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {1, 2, 3, 4, 5, 6}), "A OR B (B subset) should equal A");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, b), {1, 3, 5}), "A - B should equal {1, 3, 5}");
    TEST_ASSERT(PostingsOperations::difference(b, a).empty(), "B - A (B subset) should be empty");
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect_with_skips(a, b), {2, 4, 6}), "Skip A AND B failed");
}


// Test 7: Single-element lists

void test_7_single_element_lists() {
    PostingList a = makeList({42});
    PostingList b = makeList({42});
    PostingList c = makeList({99});

    // Matching singletons
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect(a, b), {42}), "Matching singletons AND failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {42}), "Matching singletons OR failed");
    TEST_ASSERT(PostingsOperations::difference(a, b).empty(), "Matching singletons NOT failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect_with_skips(a, b), {42}), "Matching singletons skip failed");

    // Non-matching singletons
    TEST_ASSERT(PostingsOperations::intersect(a, c).empty(), "Non-matching singletons AND failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, c), {42, 99}), "Non-matching singletons OR failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, c), {42}), "Non-matching singletons NOT failed");
    TEST_ASSERT(PostingsOperations::intersect_with_skips(a, c).empty(), "Non-matching singletons skip failed");
}


// Test 8: Single matching document among many

void test_8_single_matching_document() {
    PostingList a = makeList({1, 3, 5, 7, 9});
    PostingList b = makeList({2, 4, 5, 8, 10});

    TEST_ASSERT(checkDocIds(PostingsOperations::intersect(a, b), {5}), "Single match AND failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {1, 2, 3, 4, 5, 7, 8, 9, 10}), "Single match OR failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, b), {1, 3, 7, 9}), "Single match NOT failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect_with_skips(a, b), {5}), "Single match skip failed");
}


// Test 9: No matching documents

void test_9_no_matching_documents() {
    PostingList a = makeList({10, 20, 30});
    PostingList b = makeList({40, 50, 60});

    TEST_ASSERT(PostingsOperations::intersect(a, b).empty(), "No match AND failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(a, b), {10, 20, 30, 40, 50, 60}), "No match OR failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(a, b), {10, 20, 30}), "No match NOT failed");
    TEST_ASSERT(PostingsOperations::intersect_with_skips(a, b).empty(), "No match skip failed");
}


// Test 10: Lists with very different lengths

void test_10_different_lengths() {
    PostingList shortList = makeList({50});
    vector<int> longVec;
    for (int i = 1; i <= 100; i++) {
        longVec.push_back(i);
    }
    PostingList longList = makeList(longVec);

    TEST_ASSERT(checkDocIds(PostingsOperations::intersect(shortList, longList), {50}), "Short AND Long failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::union_(shortList, longList), longVec), "Short OR Long failed");
    TEST_ASSERT(PostingsOperations::difference(shortList, longList).empty(), "Short - Long should be empty");

    vector<int> expectedNot;
    for (int i = 1; i <= 100; i++) {
        if (i != 50) expectedNot.push_back(i);
    }
    TEST_ASSERT(checkDocIds(PostingsOperations::difference(longList, shortList), expectedNot), "Long - Short failed");
    TEST_ASSERT(checkDocIds(PostingsOperations::intersect_with_skips(shortList, longList), {50}), "Short AND Long skip failed");
}


// Test 11: Preservation of document IDs, frequencies, and positions

void test_11_metadata_preservation() {
    Posting pa2(2, 5, {1, 3, 5, 7, 9});
    Posting pa4(4, 2, {10, 20});
    PostingList a = makeListFromPostings({pa2, pa4});

    Posting pb2(2, 1, {99});
    Posting pb6(6, 3, {100, 200, 300});
    PostingList b = makeListFromPostings({pb2, pb6});

    // Intersection: matching doc 2 should preserve left operand 'a' metadata
    PostingList andRes = PostingsOperations::intersect(a, b);
    TEST_ASSERT(andRes.size() == 1, "Intersect size should be 1");
    const Posting& postAnd = andRes.get(0);
    TEST_ASSERT(postAnd.get_doc_id() == 2, "Intersect docId should be 2");
    TEST_ASSERT(postAnd.get_frequency() == 5, "Intersect frequency should be from left operand (5)");
    TEST_ASSERT(postAnd.get_positions() == vector<int>({1, 3, 5, 7, 9}), "Intersect positions from left operand");

    // Difference: doc 4 in A - B preserves A's metadata
    PostingList notRes = PostingsOperations::difference(a, b);
    TEST_ASSERT(notRes.size() == 1, "Difference size should be 1");
    const Posting& postNot = notRes.get(0);
    TEST_ASSERT(postNot.get_doc_id() == 4, "Difference docId should be 4");
    TEST_ASSERT(postNot.get_frequency() == 2, "Difference frequency preserved");
    TEST_ASSERT(postNot.get_positions() == vector<int>({10, 20}), "Difference positions preserved");

    // Union:
    // doc 2 in both -> preserved from A
    // doc 4 in A only -> preserved from A
    // doc 6 in B only -> preserved from B
    PostingList orRes = PostingsOperations::union_(a, b);
    TEST_ASSERT(orRes.size() == 3, "Union size should be 3");
    TEST_ASSERT(orRes.get(0).get_doc_id() == 2 && orRes.get(0).get_frequency() == 5, "Union doc 2 metadata from A");
    TEST_ASSERT(orRes.get(1).get_doc_id() == 4 && orRes.get(1).get_frequency() == 2, "Union doc 4 metadata from A");
    TEST_ASSERT(orRes.get(2).get_doc_id() == 6 && orRes.get(2).get_frequency() == 3, "Union doc 6 metadata from B");
    TEST_ASSERT(orRes.get(2).get_positions() == vector<int>({100, 200, 300}), "Union doc 6 positions from B");
}


// Test 12: Large posting lists (performance)

void test_12_large_posting_lists() {
    const int N = 10000;
    vector<int> vecA;
    vector<int> vecB;
    vector<int> expectedAnd;

    // A = even numbers [0, 2, 4, ..., 2N-2]
    // B = multiples of 3 [0, 3, 6, ..., 3N-3]
    for (int i = 0; i < N; i++) {
        vecA.push_back(2 * i);
    }
    for (int i = 0; i < N; i++) {
        vecB.push_back(3 * i);
    }

    PostingList a = makeList(vecA);
    PostingList b = makeList(vecB);

    auto start = chrono::high_resolution_clock::now();
    PostingList andRes = PostingsOperations::intersect(a, b);
    auto endAnd = chrono::high_resolution_clock::now();

    PostingList orRes = PostingsOperations::union_(a, b);
    auto endOr = chrono::high_resolution_clock::now();

    PostingList notRes = PostingsOperations::difference(a, b);
    auto endNot = chrono::high_resolution_clock::now();

    PostingList skipRes = PostingsOperations::intersect_with_skips(a, b);
    auto endSkip = chrono::high_resolution_clock::now();

    // Expected AND: multiples of 6 up to 2*(N-1)
    int maxA = 2 * (N - 1);
    for (int i = 0; 6 * i <= maxA; i++) {
        expectedAnd.push_back(6 * i);
    }
    TEST_ASSERT(checkDocIds(andRes, expectedAnd), "Large AND match failed");
    TEST_ASSERT(checkDocIds(skipRes, expectedAnd), "Large skip AND match failed");
    TEST_ASSERT(andRes.size() == expectedAnd.size(), "Large AND size failed");

    auto andDur = chrono::duration_cast<chrono::microseconds>(endAnd - start).count();
    auto orDur = chrono::duration_cast<chrono::microseconds>(endOr - endAnd).count();
    auto notDur = chrono::duration_cast<chrono::microseconds>(endNot - endOr).count();
    auto skipDur = chrono::duration_cast<chrono::microseconds>(endSkip - endNot).count();

    cout << "    [Perf] Large Lists (N=" << N << "): AND=" << andDur << "us, OR="
         << orDur << "us, NOT=" << notDur << "us, SkipAND=" << skipDur << "us" << endl;
}


// Test 13: Memory safety — copy, move, return by value

void test_13_memory_safety_and_ownership() {
    // Copy Construction
    {
        PostingList orig = makeList({1, 2, 3});
        PostingList copy = orig;
        TEST_ASSERT(checkDocIds(copy, {1, 2, 3}), "Copy constructor failed");
        copy.add(Posting(4, 1, {0}));
        TEST_ASSERT(orig.size() == 3, "Deep copy violated: orig mutated by copy");
        TEST_ASSERT(copy.size() == 4, "Copy add failed");
    }

    // Copy Assignment
    {
        PostingList orig = makeList({10, 20});
        PostingList assign;
        assign = orig;
        TEST_ASSERT(checkDocIds(assign, {10, 20}), "Copy assignment failed");
        assign.add(Posting(30, 1, {0}));
        TEST_ASSERT(orig.size() == 2, "Deep copy assignment violated");
    }

    // Self-Assignment
    {
        PostingList selfList = makeList({5, 15, 25});
        selfList = selfList;
        TEST_ASSERT(checkDocIds(selfList, {5, 15, 25}), "Self-assignment corrupted list");
    }

    // Move Construction
    {
        PostingList source = makeList({100, 200});
        PostingList moved(std::move(source));
        TEST_ASSERT(checkDocIds(moved, {100, 200}), "Move construction failed");
        TEST_ASSERT(source.empty(), "Source should be empty after move");
    }

    // Move Assignment
    {
        PostingList source = makeList({500, 600});
        PostingList target;
        target = std::move(source);
        TEST_ASSERT(checkDocIds(target, {500, 600}), "Move assignment failed");
        TEST_ASSERT(source.empty(), "Source should be empty after move assignment");
    }

    // Return by value from PostingsOperations
    {
        PostingList a = makeList({1, 3, 5});
        PostingList b = makeList({3, 5, 7});
        PostingList res = PostingsOperations::intersect(a, b);
        TEST_ASSERT(checkDocIds(res, {3, 5}), "Return-by-value failed");
    }
}


// Test 14: Skip intersection equivalence with normal intersection

void test_14_skip_intersection_equivalence() {
    mt19937 rng(12345);
    uniform_int_distribution<int> dist(1, 5000);

    for (int trial = 0; trial < 10; trial++) {
        // Generate random doc IDs, sort and deduplicate to create valid sorted PostingLists
        vector<int> aDocs;
        vector<int> bDocs;
        int lenA = 50 + (trial * 30);
        int lenB = 60 + (trial * 35);

        for (int i = 0; i < lenA; i++) aDocs.push_back(dist(rng));
        for (int i = 0; i < lenB; i++) bDocs.push_back(dist(rng));

        // Sort and deduplicate to make valid sorted PostingLists
        sort(aDocs.begin(), aDocs.end());
        aDocs.erase(unique(aDocs.begin(), aDocs.end()), aDocs.end());
        sort(bDocs.begin(), bDocs.end());
        bDocs.erase(unique(bDocs.begin(), bDocs.end()), bDocs.end());

        PostingList a = makeList(aDocs);
        PostingList b = makeList(bDocs);

        PostingList normalAnd = PostingsOperations::intersect(a, b);
        PostingList skipAnd = PostingsOperations::intersect_with_skips(a, b);

        vector<int> normalIds = getDocIds(normalAnd);
        vector<int> skipIds = getDocIds(skipAnd);

        TEST_ASSERT(normalIds == skipIds, "Skip intersection did not match normal intersection");
    }
}

int main() {

    cout << " Mini Search Engine - Boolean Operations " << endl;
    cout << " Test Suite (Part 3)                     " << endl;
    RUN_TEST(test_baseline_example);
    RUN_TEST(test_1_both_lists_empty);
    RUN_TEST(test_2_first_list_empty);
    RUN_TEST(test_3_second_list_empty);
    RUN_TEST(test_4_disjoint_lists);
    RUN_TEST(test_5_identical_lists);
    RUN_TEST(test_6_subset_relationships);
    RUN_TEST(test_7_single_element_lists);
    RUN_TEST(test_8_single_matching_document);
    RUN_TEST(test_9_no_matching_documents);
    RUN_TEST(test_10_different_lengths);
    RUN_TEST(test_11_metadata_preservation);
    RUN_TEST(test_12_large_posting_lists);
    RUN_TEST(test_13_memory_safety_and_ownership);
    RUN_TEST(test_14_skip_intersection_equivalence);

    cout << " Total Passed: " << g_passCount << endl;
    cout << " Total Failed: " << g_failCount << endl;
    return (g_failCount == 0) ? 0 : 1;
}
