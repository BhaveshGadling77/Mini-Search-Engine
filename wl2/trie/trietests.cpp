#include<iostream>
#include<string>
#include<vector>
#include "trie.h"

using namespace std;

void printResults(vector<string> results){
    for(string s : results){
        cout << s << " ";
    }
    cout << endl;
}

int main() {
    Trie prefixTrie;
    Trie suffixTrie;

    vector <string> words = {"car", "card", "care", "cat", "dog", "apple"};
    for(string word: words){
        prefixTrie.insert(word);
        suffixTrie.insertReversed(word);
    }

    cout << "Prefix 'ca': ";
    printResults(prefixTrie.searchForPrefix("ca"));

    cout << "Prefix 'car': ";
    printResults(prefixTrie.searchForPrefix("car"));

    cout << "Prefix 'xyz': ";
    printResults(prefixTrie.searchForPrefix("xyz"));

    cout << "Suffix 'ar': ";
    printResults(suffixTrie.searchForSuffix("ar"));

    cout << "Suffix 'at': ";
    printResults(suffixTrie.searchForSuffix("at"));

    cout << "Suffix 'ple': ";
    printResults(suffixTrie.searchForSuffix("ple"));

    cout << "Suffix 'xyz': ";
    printResults(suffixTrie.searchForSuffix("xyz"));

    return 0;
}

