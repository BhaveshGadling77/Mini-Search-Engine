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
    Trie trie;

    vector <string> words = {"car", "card", "care", "cat", "dog", "apple","cards","carding"};
    for(string word: words){
        trie.insert(word);
        trie.insertReversed(word);
    }

    cout << "Prefix 'ca': ";
    printResults(trie.searchForPrefix("ca"));

    cout << "Prefix 'car': ";
    printResults(trie.searchForPrefix("car"));

    cout << "Prefix 'xyz': ";
    printResults(trie.searchForPrefix("xyz"));

    cout << "Suffix 'ar': ";
    printResults(trie.searchForSuffix("ar"));

    cout << "Suffix 'at': ";
    printResults(trie.searchForSuffix("at"));

    cout << "Suffix 'ple': ";
    printResults(trie.searchForSuffix("ple"));

    cout << "Suffix 'xyz': ";
    printResults(trie.searchForSuffix("xyz"));

    cout << "*ar*: ";
    printResults(trie.searchForInfixWildCard("ard"));

    return 0;
}

