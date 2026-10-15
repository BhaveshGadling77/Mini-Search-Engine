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


void Trie::insertInto(string word, TrieNode* start){
    if(word.empty()) {
        return;
    }
    TrieNode* node = start;
    int i = 0;                                
    int n = word.size();

    while(i < n){
        int idx = word[i] - 'a';
        TrieNode* child = node->children[idx];

        
        if(child == nullptr){
            TrieNode* leaf = new TrieNode(word.substr(i));
            leaf->endOfWord = true;
            node->children[idx] = leaf;
            return;
        }

        int labelLen = child->label.size();
        int j = 0;
        while(j < labelLen && i + j < n && child->label[j] == word[i + j]){
            j++;
        }

        if(j == labelLen){
            node = child;
            i += j;
            continue;
        }

        TrieNode* mid = new TrieNode(child->label.substr(0, j));
        child->label = child->label.substr(j);
        mid->children[child->label[0] - 'a'] = child;
        node->children[idx] = mid;
        i += j;

        if(i == n){
            mid->endOfWord = true;              
        }
        else{
            TrieNode* leaf = new TrieNode(word.substr(i));
            leaf->endOfWord = true;
            mid->children[word[i] - 'a'] = leaf;
        }
        return;
    }
    node->endOfWord = true;
}

void Trie::insert(string word){
    int n = word.size();
    for(int i = 0; i <= n - k; i++){
        string sub = word.substr(i, k);
        kgramIndex[sub].insert(word);
    }
    insertInto(word, root);
}

void Trie::insertReversed(string word){
    reverseWord(word);
    insertInto(word, revRoot);      
}

TrieNode* Trie::search(string word, TrieNode* start, string &built){
    TrieNode* node = start;
    built = "";
    int i = 0;
    int n = word.size();
    while(i < n){
        TrieNode* child = node->children[word[i] - 'a'];
        if(child == nullptr){
            return nullptr;
        }
        int labelLen = child->label.size();
        for(int j = 0; j < labelLen && i + j < n; j++){
            if(child->label[j] != word[i + j]){
                return nullptr;
            }
        }
        built += child->label;
        i += labelLen;
        node = child;
    }
    return node;
}

void Trie::backTrackTrie(vector<string> & results, TrieNode* node, string &w){
    if(node->endOfWord == true && w.size() != 0){
        results.push_back(w);
    }
    for(int i = 0; i < 26; i++){
        if(node->children[i] != nullptr){
            TrieNode* child = node->children[i];
            w += child->label;
            backTrackTrie(results, child, w);
            w.erase(w.size() - child->label.size());
        }
    }
}

vector<string> Trie::getResults(string word, TrieNode* start){
    string w;
    TrieNode* r = search(word, start, w);
    if(r == nullptr){
        return {};
    }
    vector<string> results;
    backTrackTrie(results, r, w);
    return results;
}

vector<string> Trie::searchForPrefix(string word){
    vector<string> result = getResults(word, root);
    return result;
}

vector<string> Trie::searchForSuffix(string word){
    reverseWord(word);
    vector<string> result = getResults(word, revRoot);
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
    int n = word.size();
    vector<string> result;

    if(n < k){
        vector<string> all = getResults("", root);
        for(string &w : all){
            if(w.find(word) != string::npos){
                result.push_back(w);
            }
        }
        return result;
    }

    unordered_set<string> cur;
    for(int i = 0; i <= n - k; i++){
        string gram = word.substr(i, k);
        auto it = kgramIndex.find(gram);
        if(it == kgramIndex.end()){
            return {};                  
        }

        if(i == 0){
            cur = it->second;
        }
        else{
            unordered_set<string> next;
            for(const string &w : cur){
                if(it->second.count(w)){
                    next.insert(w);
                }
            }
            cur = std::move(next);
        }

        if(cur.empty()){
            return {};
        }
    }

    for(const string &w : cur){
        if(w.find(word) != string::npos){
            result.push_back(w);
        }
    }
    return result;
}