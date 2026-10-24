#ifndef WL2_TEXT_PROCESSING_H
#define WL2_TEXT_PROCESSING_H

#include <string>
#include <vector>

namespace wl2 {
// Shared English preprocessing used by both index construction and queries.
std::string normalize_token(const std::string &token);
bool is_stopword(const std::string &token);
std::string lemmatize(const std::string &token);
std::vector<std::string> tokenize(const std::string &text);
std::vector<std::string> process_text(const std::string &text);
} // namespace wl2

#endif
