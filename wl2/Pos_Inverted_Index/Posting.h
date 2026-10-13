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

#endif