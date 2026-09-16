#pragma once
#include<iostream>
#include"trie.h"
#include<string>
#include<vector>

using namespace std;

void Trie::reverseWord(string &word){
    int l = 0, r = word.size() - 1;
    while(l <= r){
        char temp = word[l];
        word[l] = word[r];
        word[r] = temp;
        l++;
        r--;
    }
}

void Trie::insert(string word){
    TrieNode* node = root;
    for(char c : word){
        int index = c - 'a';
        if(node->children[index] ==  nullptr){
            node->children[index] = new TrieNode();
        }
        node = node->children[index];
    }
    node->endOfWord = true;
}

void Trie::insertReversed(string word){
    reverseWord(word);
    insert(word);
}
TrieNode* Trie::search(string word){
    TrieNode* node = root;
    for(char c : word){
        int index = c - 'a';
        if(node->children[index] == nullptr){
            return nullptr;
        }
        node = node->children[index];
    }
    return node;
}

void Trie::backTrackTrie(vector<string> & results, TrieNode* node, string &w){
    if(node->endOfWord == true && w.size() != 0){
        results.push_back(w);
    }
    for(int i = 0; i < 26; i++){
        if(node->children[i] != nullptr){
            w.push_back(i + 'a');
            backTrackTrie(results, node->children[i], w);
            w.pop_back();
        }
    }
}

vector<string> Trie::getResults(string word){
    TrieNode* r = search(word);
    if(r == nullptr){
        return {};
    }
    vector<string> results;
    string w = word;
    backTrackTrie(results, r, w);
    return results;
}

vector<string> Trie::searchForPrefix(string word){
    vector<string> result = getResults(word);
    return result;
}

vector<string> Trie::searchForSuffix(string word){
    reverseWord(word);
    vector<string> result = getResults(word);
    for(int i = 0; i < result.size(); i++){
        reverseWord(result[i]);
    }
    return result;
}

