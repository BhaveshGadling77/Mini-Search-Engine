#include "query_parser.h"
#include <algorithm>
#include <cctype>
#include <sstream>
#include <set>
#include <functional>
#include <cstdint>

namespace {
const std::vector<Document>* docs=nullptr;
std::unordered_map<int,std::unordered_map<std::string,int>> terms;
std::unordered_map<std::string,int> df;
std::string version="uninitialized";
std::string norm(std::string s){for(char& c:s)c=char(std::tolower((unsigned char)c));return s;}
std::vector<std::string> words(const std::string& s){std::vector<std::string> r;std::string w;for(unsigned char c:s){if(std::isalnum(c)||c=='_'||c=='*')w+=char(std::tolower(c));else if(!w.empty()){r.push_back(w);w.clear();}}if(!w.empty())r.push_back(w);return r;}
}
void initialize_query_processor(const std::vector<Document>* input){docs=input;terms.clear();df.clear();if(!docs)return;uint64_t hash=14695981039346656037ULL;for(auto& d:*docs){auto& t=terms[d.docId];hash^=uint64_t(d.docId);hash*=1099511628211ULL;for(auto x:d.tokens){x=norm(x);++t[x];for(unsigned char c:x){hash^=c;hash*=1099511628211ULL;}}for(auto& x:t)++df[x.first];}version="w2-"+std::to_string(docs->size())+"-"+std::to_string(hash);}
QueryResult resolve_query(const std::string& q){
 QueryResult out;if(!docs)return out;const auto query=words(q);std::set<std::string> qt;for(auto&w:query)if(w!="and"&&w!="or"&&w!="not")qt.insert(w);
 const bool phrase=q.find('"')!=std::string::npos, use_or=q.find(" OR ")!=std::string::npos, negate=q.size()>=3&&norm(q.substr(0,3))=="not";
 std::vector<std::string> expanded;for(auto&w:qt){if(w.find('*')==std::string::npos){if(df.count(w))expanded.push_back(w);}else{const auto star=w.find('*');const std::string prefix=w.substr(0,star),suffix=w.substr(star+1);for(auto&entry:df)if(entry.first.compare(0,prefix.size(),prefix)==0&&entry.first.size()>=suffix.size()&&entry.first.compare(entry.first.size()-suffix.size(),suffix.size(),suffix)==0)expanded.push_back(entry.first);}}
 std::set<int> matches;
 if(negate){for(auto&d:*docs){bool excluded=false;for(auto&w:expanded)if(terms[d.docId].count(w))excluded=true;if(!excluded)matches.insert(d.docId);}}
 else
 for(auto& d:*docs){auto& counts=terms[d.docId];bool ok=false;
  if(phrase){auto it=std::search(d.tokens.begin(),d.tokens.end(),query.begin(),query.end(),[](const std::string&a,const std::string&b){return b=="and"||b=="or"||b=="not"||norm(a)==b;});ok=it!=d.tokens.end();}
  else {int found=0;for(auto&w:expanded)if(counts.count(w))++found;if(negate)ok=found==0;else ok=use_or?found>0:(!expanded.empty()&&found==(int)expanded.size());}
  if(ok) matches.insert(d.docId);
 }
 for(auto&w:expanded) out.doc_freq[w]=df[w];
 for(int id:matches) { auto& candidate=out.candidates[id]; for(auto&w:expanded){int n=terms[id][w];if(n)candidate[w]=n;} }
 return out;
}
CorpusStats get_corpus_stats(){size_t n=0;if(docs)for(auto&d:*docs)n+=d.tokens.size();return {docs?(int)docs->size():0,docs&&!docs->empty()?double(n)/docs->size():0.0};}
std::string get_index_version(){return version;}
std::unordered_map<int,DocSnippetData> get_doc_snippet_data(const std::vector<int>& ids){std::unordered_map<int,DocSnippetData> r;if(!docs)return r;for(auto id:ids)for(auto&d:*docs)if(d.docId==id){DocSnippetData v{d.title,d.url,d.text};if(v.text.empty())for(auto&t:d.tokens){if(!v.text.empty())v.text+=' ';v.text+=t;}r[id]=v;break;}return r;}
std::unordered_map<int,std::unordered_map<std::string,int>> get_doc_terms(const std::vector<int>& ids){std::unordered_map<int,std::unordered_map<std::string,int>>r;if(!docs)return r;for(int id:ids)for(const auto&d:*docs)if(d.docId==id){auto&counts=r[id];for(const auto&t:d.tokens)++counts[norm(t)];break;}return r;}
