#pragma once
#include<iostream>
#include<string>
#include<vector>
#include <unordered_map>

using namespace std;

class TrieNode{
    public:
        bool endOfWord;
        TrieNode* children[26];

        TrieNode(){
            endOfWord = false;
            for(int i = 0; i < 26; i++){
                children[i] = nullptr;
            }
        }
};

class Trie{
    private:
        TrieNode* root;
        unordered_map<string, unordered_set<string>> kgramIndex;
        int k = 3;
    public:
        Trie(){
            root = new TrieNode();
        }
        void insert(string word);
        void insertReversed(string word);
        vector<string> searchForSuffix(string word);
        vector<string> searchForPrefix(string word);
        vector<string> searchForWildCard(string prefix, string suffix);
        vector<string> searchForInfixWildCard(string word);
        TrieNode* search(string word);
        void deleteWord(string word);
        vector<string> getResults(string word);
        void reverseWord(string &word);
        void backTrackTrie(vector<string> &result, TrieNode* node, string &w);
};