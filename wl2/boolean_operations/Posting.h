#ifndef POSTING_H
#define POSTING_H

#include <vector>
#include <iostream>
#include <algorithm>
#include <stdexcept>

using namespace std;

struct Posting {
    int docId;
    vector<int> positions;
    int frequency;

    Posting() : docId(0), frequency(0) {}

    Posting(int doc_id, int freq = 0)
        : docId(doc_id), frequency(freq) {}

    Posting(int doc_id, int freq, const vector<int>& pos)
        : docId(doc_id), positions(pos), frequency(freq) {}

    Posting(int doc_id, const vector<int>& pos)
        : docId(doc_id), positions(pos), frequency(static_cast<int>(pos.size())) {}

    int get_doc_id() const {
        return docId;
    }

    int get_frequency() const {
        return frequency;
    }

    const vector<int>& get_positions() const {
        return positions;
    }

    bool has_position(int position) const {
        for (int pos : positions) {
            if (pos == position) return true;
        }
        return false;
    }

    bool operator==(const Posting& other) const {
        return docId == other.docId;
    }

    bool operator!=(const Posting& other) const {
        return docId != other.docId;
    }

    bool operator<(const Posting& other) const {
        return docId < other.docId;
    }
};

/**
 * @brief PostingList backed by dynamic array.
 *
 * Implements:
 * - add(const Posting& posting)
 * - get(size_t index) const
 * - get_all() const
 */
class PostingList {
private:
    vector<Posting> postings;

public:
    PostingList() = default;

    // Adds a posting while maintaining ascending order by docId and merging duplicates internally
    void add(const Posting& posting) {
        if (postings.empty() || postings.back().docId < posting.docId) {
            postings.push_back(posting);
            return;
        }

        auto it = lower_bound(postings.begin(), postings.end(), posting.docId,
            [](const Posting& p, int id) {
                return p.docId < id;
            });

        if (it != postings.end() && it->docId == posting.docId) {
            for (int pos : posting.positions) {
                it->positions.push_back(pos);
            }
            sort(it->positions.begin(), it->positions.end());
            it->positions.erase(unique(it->positions.begin(), it->positions.end()), it->positions.end());
            it->frequency = static_cast<int>(it->positions.size());
        } else {
            postings.insert(it, posting);
        }
    }

    // Adds a term occurrence; maintains ascending order by docId and handles duplicates internally
    void addOccurrence(int docId, int pos) {
        if (!postings.empty() && postings.back().docId == docId) {
            auto& p = postings.back();
            if (p.positions.empty() || p.positions.back() < pos) {
                p.positions.push_back(pos);
                p.frequency++;
            } else if (p.positions.back() > pos) {
                auto posIt = lower_bound(p.positions.begin(), p.positions.end(), pos);
                if (posIt == p.positions.end() || *posIt != pos) {
                    p.positions.insert(posIt, pos);
                    p.frequency++;
                }
            }
            return;
        }

        if (postings.empty() || postings.back().docId < docId) {
            Posting newPosting;
            newPosting.docId = docId;
            newPosting.positions.push_back(pos);
            newPosting.frequency = 1;
            postings.push_back(newPosting);
            return;
        }

        auto it = lower_bound(postings.begin(), postings.end(), docId,
            [](const Posting& p, int id) {
                return p.docId < id;
            });

        if (it != postings.end() && it->docId == docId) {
            auto posIt = lower_bound(it->positions.begin(), it->positions.end(), pos);
            if (posIt == it->positions.end() || *posIt != pos) {
                it->positions.insert(posIt, pos);
                it->frequency++;
            }
        } else {
            Posting newPosting;
            newPosting.docId = docId;
            newPosting.positions.push_back(pos);
            newPosting.frequency = 1;
            postings.insert(it, newPosting);
        }
    }

    const Posting& get(size_t index) const {
        if (index >= postings.size()) {
            throw out_of_range("PostingList index out of range");
        }
        return postings[index];
    }

    const vector<Posting>& get_all() const {
        return postings;
    }

    size_t size() const {
        return postings.size();
    }

    bool empty() const {
        return postings.empty();
    }

    void clear() {
        postings.clear();
    }

    // Standard vector iteration support
    auto begin() const { return postings.begin(); }
    auto end() const { return postings.end(); }
    auto cbegin() const { return postings.cbegin(); }
    auto cend() const { return postings.cend(); }

    void print() const {
        for (const auto& p : postings) {
            cout << "    Doc ID: " << p.docId << endl;
            cout << "    Positions: [";
            for (size_t i = 0; i < p.positions.size(); i++) {
                cout << p.positions[i];
                if (i + 1 < p.positions.size()) cout << ", ";
            }
            cout << "]" << endl;
            cout << "    Frequency: " << p.frequency << endl << endl;
        }
    }
};

#endif // POSTING_H
