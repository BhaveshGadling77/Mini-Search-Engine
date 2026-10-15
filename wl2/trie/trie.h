#pragma once
#include<iostream>
#include<string>
#include<vector>
#include <unordered_map>
#include <unordered_set>

using namespace std;

class TrieNode{
    public:
        string label;               // edge label leading INTO this node
        bool endOfWord;
        TrieNode* children[26];     // indexed by first char of the child's label

        TrieNode(string l = ""){
            label = l;
            endOfWord = false;
            for(int i = 0; i < 26; i++){
                children[i] = nullptr;
            }
        }
    }
};

class Trie{
    private:
        TrieNode* root;             // forward words
        TrieNode* revRoot;          // reversed words (for suffix search)
        unordered_map<string, unordered_set<string>> kgramIndex;
        int k = 3;
        void insertInto(string word, TrieNode* start);
    public:
        Trie(){
            root = new TrieNode();
            revRoot = new TrieNode();
        }
        void insert(string word);
        void insertReversed(string word);
        vector<string> searchForSuffix(string word);
        vector<string> searchForPrefix(string word);
        vector<string> searchForWildCard(string prefix, string suffix);
        vector<string> searchForInfixWildCard(string word);
        TrieNode* search(string word, TrieNode* start, string &built);
        void deleteWord(string word);
        vector<string> getResults(string word, TrieNode* start);
        void reverseWord(string &word);
        void backTrackTrie(vector<string> &result, TrieNode* node, string &w);
};