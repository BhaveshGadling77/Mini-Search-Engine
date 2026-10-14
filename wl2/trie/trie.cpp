#pragma once
#include<iostream>
#include"trie.h"
#include<string>
#include<vector>
#include <unordered_set>
#include <unordered_map>
#include <algorithm>

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
    int n = word.size();
    for(int i = 0; i <= n - k; i++){
        string sub = word.substr(i, k);
        kgramIndex[sub].insert(word);
    }
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

vector<string> Trie::searchForWildCard(string prefix, string suffix){
    vector<string> pre = searchForPrefix(prefix);
    vector<string> suf = searchForSuffix(suffix);
    unordered_set<string> p;
    unordered_set<string> s;
    for(string str: pre){
        p.insert(str);
    }
    for(string str: suf){
        s.insert(str);
    }
    vector<string> result;
    for(auto &word: p){
        if(s.find(word) != s.end()){
            result.push_back(word);
        }
    }
    return result;
}

vector<string> Trie::searchForInfixWildCard(string word){
    if(word.size() < k){
        return {};
    }
    int n = word.size();
    vector<string> result;
    unordered_set <string> s1;
    unordered_set<string> res;
    for(int i = 0; i <= n - k; i++){
        string str = word.substr(i,k);
        if(s1.empty() == true){
            s1 = kgramIndex[str];
            res = s1;
        }
        else{
            unordered_set<string> s2 = kgramIndex[str];
            set_intersection(s1.begin(), s1.end(), s2.begin(), s2.end(), inserter(res, res.begin()));
            s1 = res;
        }
    }
    for(auto &p: res){
        result.push_back(p);
    }
    return result;
}