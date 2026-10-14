# Boolean Operations

`PostingsOperations` combines two already-resolved `PostingList` objects. It does not accept query strings or look up terms in the index. Resolve each term or phrase first, then pass the resulting lists to an operation.

```cpp
PostingList* base_list = index.get("base");
PostingList* ball_list = index.get("ball");

if (base_list != nullptr && ball_list != nullptr) {
    PostingList matching_documents =
        PostingsOperations::boolean_and(*base_list, *ball_list);
}
```

The operations use the `PostingList` type from `Inverted_Index/Posting.h`. Lists must be sorted by document ID, as the inverted index produces them.

## Operations

| Method | Result |
| --- | --- |
| `intersect(a, b)` or `boolean_and(a, b)` | Documents present in both lists |
| `union_(a, b)` or `boolean_or(a, b)` | Documents present in either list, without duplicate document IDs |
| `difference(a, b)` or `boolean_not(a, b)` | Documents in `a` that are absent from `b` |
| `intersect_with_skips(a, b)` | Same document IDs as intersection, using index jumps to skip ahead in sorted lists |

Each method returns a `PostingList`. `boolean_not(a, b)` is the difference `a - b`; it does not compute a corpus-wide complement. `extract_doc_ids(list)` returns just the document IDs as a `vector<int>`.

For a document present in both inputs, intersection and union keep the posting data from the left list. Difference keeps the posting data from its left input. The operations do not merge term frequencies or positions across lists.

## Complexity

The regular intersection, union, and difference scan their inputs with sorted two-pointer merges in O(m + n) time for input lists of sizes `m` and `n`. Building the returned list adds work because `PostingList::addOccurrence` searches the existing entries for each appended document. `intersect_with_skips` uses square-root-sized index jumps; it has the same output as regular intersection, but its speed depends on the list sizes and overlap pattern.

## Tests and benchmark

From the repository root:

```bash
make -C wl2 test
make -C wl2 benchmark
```

The tests check list results, posting data preservation, empty and boundary cases, and many generated sorted inputs. The benchmark compares intersection with and without skip pointers on dense, disjoint, and sparse inputs. Benchmark timings vary by machine and workload; use them as measurements for those inputs, not as a guarantee for every query.
