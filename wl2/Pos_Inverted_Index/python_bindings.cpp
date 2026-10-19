#include "query_parser.h"
#include <pybind11/pybind11.h>
using namespace pybind11::literals;
#include <pybind11/stl.h>
namespace py = pybind11;
PYBIND11_MODULE(wl2bridge, m) {
    m.doc() = "Worklet 2 query bridge. Call initialize(corpus_path) before the five API functions.";
    m.def("initialize", [](const std::string &path) {
        static std::vector<Document> docs;
        docs = readDocuments(path);
        initialize_query_processor(&docs);
        return docs.size();
    });
    m.def("resolve_query", [](const std::string &q) {
        auto r = resolve_query(q);
        return py::make_tuple(r.candidates, r.doc_freq);
    });
    m.def("get_corpus_stats", []() {
        auto s = get_corpus_stats();
        return py::dict("total_docs"_a = s.total_docs, "avg_doc_length"_a = s.avg_doc_length);
    });
    m.def("get_index_version", &get_index_version);
    m.def("get_doc_snippet_data", [](const std::vector<int> &ids) {
        py::dict r;
        for (auto &x : get_doc_snippet_data(ids))
            r[py::int_(x.first)] = py::dict("title"_a = x.second.title, "url"_a = x.second.url,
                                            "text"_a = x.second.text);
        return r;
    });
    m.def("get_doc_terms", &get_doc_terms);
}
