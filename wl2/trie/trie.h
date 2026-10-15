#pragma once
#include<iostream>
#include<string>
#include<vector>

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
    public:
        Trie(){
            root = new TrieNode();
        }
        void insert(string word);
        void insertReversed(string word);
        vector<string> searchForSuffix(string word);
        vector<string> searchForPrefix(string word);
        TrieNode* search(string word);
        void deleteWord(string word);
        vector<string> getResults(string word);
        void reverseWord(string &word);
        void backTrackTrie(vector<string> &result, TrieNode* node, string &w);
};