// Demonstrates WHY skip pointers help a union, using the same algorithm as
// PostingsOperations::union_with_skips but on plain docId vectors, so that the
// cost of copying Posting objects (positions vectors) does not hide the effect.
//
// Reports (1) docId comparisons and (2) wall time for plain merge vs skip merge,
// and checks both produce identical output.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <vector>

using Ids = std::vector<int>;
static long comparisons = 0;

static Ids plain_union(const Ids &a, const Ids &b) {
    Ids r;
    r.reserve(a.size() + b.size());
    size_t i = 0, j = 0;
    while (i < a.size() && j < b.size()) {
        ++comparisons;
        if (a[i] == b[j]) { r.push_back(a[i]); ++i; ++j; }
        else { ++comparisons; r.push_back(a[i] < b[j] ? a[i++] : b[j++]); }
    }
    while (i < a.size()) r.push_back(a[i++]);
    while (j < b.size()) r.push_back(b[j++]);
    return r;
}

// Skip pointer every `stride` entries; follow it only while its target is still
// strictly smaller than the other list's current id, then bulk-copy the block.
static size_t jump(const Ids &l, size_t pos, int target, size_t stride) {
    while (pos % stride == 0 && pos + stride < l.size() && (++comparisons, l[pos + stride] < target))
        pos += stride;
    return pos;
}

static Ids skip_union(const Ids &a, const Ids &b) {
    Ids r;
    r.reserve(a.size() + b.size());
    const size_t sa = std::max<size_t>(1, (size_t)std::sqrt((double)a.size()));
    const size_t sb = std::max<size_t>(1, (size_t)std::sqrt((double)b.size()));
    size_t i = 0, j = 0;
    while (i < a.size() && j < b.size()) {
        ++comparisons;
        if (a[i] == b[j]) { r.push_back(a[i]); ++i; ++j; }
        else {
            ++comparisons;
            if (a[i] < b[j]) {
                size_t n = jump(a, i, b[j], sa); if (n == i) n = i + 1;
                r.insert(r.end(), a.begin() + i, a.begin() + n); i = n;
            } else {
                size_t n = jump(b, j, a[i], sb); if (n == j) n = j + 1;
                r.insert(r.end(), b.begin() + j, b.begin() + n); j = n;
            }
        }
    }
    while (i < a.size()) r.push_back(a[i++]);
    while (j < b.size()) r.push_back(b[j++]);
    return r;
}

static void compare(const char *name, const Ids &a, const Ids &b) {
    comparisons = 0;
    const Ids expected = plain_union(a, b);
    const long plain_cmp = comparisons;
    comparisons = 0;
    const Ids actual = skip_union(a, b);
    const long skip_cmp = comparisons;
    if (actual != expected) { std::cerr << "MISMATCH in " << name << '\n'; std::exit(1); }

    auto time_us = [&](Ids (*f)(const Ids &, const Ids &)) {
        const auto t0 = std::chrono::steady_clock::now();
        for (int k = 0; k < 200; ++k) f(a, b);
        return std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / 200;
    };
    const double plain_t = time_us(plain_union), skip_t = time_us(skip_union);
    std::cout << name << "  (A=" << a.size() << ", B=" << b.size() << ", union=" << expected.size()
              << ", outputs identical)\n"
              << "  plain merge: " << plain_cmp << " comparisons, " << plain_t << " us\n"
              << "  skip merge : " << skip_cmp << " comparisons, " << skip_t << " us  ("
              << (double)plain_cmp / skip_cmp << "x fewer comparisons, "
              << plain_t / skip_t << "x faster)\n\n";
}

int main() {
    Ids huge, tiny, c1, c2;
    for (int i = 0; i < 200000; ++i) huge.push_back(i);
    for (int i = 0; i < 10; ++i) tiny.push_back(i * 20000);
    for (int c = 0; c < 50; ++c)
        for (int k = 0; k < 2000; ++k) { c1.push_back(c * 4000 + k); c2.push_back(c * 4000 + 2000 + k); }
    Ids dense_a, dense_b;
    for (int i = 0; i < 100000; ++i) { if (i % 2 == 0) dense_a.push_back(i); else dense_b.push_back(i); }

    compare("Tiny list vs huge list", huge, tiny);
    compare("Clustered runs, no overlap", c1, c2);
    compare("Interleaved (worst case for skips)", dense_a, dense_b);
}
