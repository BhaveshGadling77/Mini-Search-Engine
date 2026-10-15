/* #ifndef POSTING_H
#define POSTING_H

#include <vector>
#include <iostream>
using namespace std;

struct Posting {
    int docId;
    vector<int> positions;
    int frequency;
};

//linked list for single words
class PostingList {
private:
    struct Node {
        Posting post;
        Node* next;
    };
    Node* head;

public:
    PostingList() {
        head = nullptr;
    }

    ~PostingList() {
        Node* cur = head;
        while (cur != nullptr) {
            Node* temp = cur;
            cur = cur->next;
            delete temp;
        }
    }

    void addOccurrence(int docId, int pos) {
        //check doc already exist
        Node* cur = head;
        while (cur != nullptr) {
            if (cur->post.docId == docId) {
                cur->post.positions.push_back(pos);
                cur->post.frequency++;
                return;
            }
            cur = cur->next;
        }

        //not found, add new at start
        Node* newNode = new Node();
        newNode->post.docId = docId;
        newNode->post.positions.push_back(pos);
        newNode->post.frequency = 1;
        newNode->next = head;
        head = newNode;
    }

    void print() const {
        Node* cur = head;
        while (cur != nullptr) {
            cout << "    Doc ID: " << cur->post.docId << endl;
            cout << "    Positions: [";
            for (size_t i = 0; i < cur->post.positions.size(); i++) {
                cout << cur->post.positions[i];
                if (i + 1 < cur->post.positions.size()) cout << ", ";
            }
            cout << "]" << endl;
            cout << "    Frequency: " << cur->post.frequency << endl << endl;
            cur = cur->next;
        }
    }
};

#endif */
/*

#ifndef POSTING_H
#define POSTING_H

#include <vector>
#include <iostream>
using namespace std;

struct Posting {
    int docId;
    vector<int> positions;
    int frequency;
};

// Posting list for a single word using vector
class PostingList {
private:
    vector<Posting> postings;

public:
    PostingList() {
        // Vector is initially empty
    }

    void addOccurrence(int docId, int pos) {
        // Check if document already exists
        for (size_t i = 0; i < postings.size(); i++) {
            if (postings[i].docId == docId) {
                postings[i].positions.push_back(pos);
                postings[i].frequency++;
                return;
            }
        }

        // Document not found: create a new posting
        Posting newPost;
        newPost.docId = docId;
        newPost.positions.push_back(pos);
        newPost.frequency = 1;

        // Insert at the beginning, like the linked list
        // Find the correct position based on docId
        auto it = postings.begin();

        while (it != postings.end() && it->docId < docId) {
            it++;
        }

        // Insert in ascending order
        postings.insert(it, newPost);
    }

    void print() const {
        for (size_t i = 0; i < postings.size(); i++) {
            cout << "    Doc ID: "
                 << postings[i].docId << endl;

            cout << "    Positions: [";

            for (size_t j = 0;
                 j < postings[i].positions.size(); j++) {
                cout << postings[i].positions[j];

                if (j + 1 < postings[i].positions.size())
                    cout << ", ";
            }

            cout << "]" << endl;

            cout << "    Frequency: "
                 << postings[i].frequency << endl << endl;
        }
    }
};

#endif
*/

#ifndef POSTING_H
#define POSTING_H

#include <vector>
#include <iostream>
using namespace std;

struct Posting {
    int docId;
    vector<int> positions;
    int frequency;
};

class PostingList {
private:
    vector<Posting> postings;

public:
    //PostingList();

    void addOccurrence(int docId, int pos);

    const vector<Posting>& get_all() const;

    void print() const;

    //to sort postings by document ID
    void sortPostings();
};

#endif
