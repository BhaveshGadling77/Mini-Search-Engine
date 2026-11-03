CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2

ROOT := .
BUILD := $(ROOT)/build

W2 := wl2/Inverted_Index
OPS := wl2/boolean_operations
PARSER := wl2/Pos_Inverted_Index
TEXT := wl2/lib/src/libfreeling/text_processing.cc
TRIE := wl2/trie

.PHONY: all cli test test-wl2 test-boolean run trie lemma clean pybind benchmark-union-small benchmark-union-big benchmark-skip-offsets storetime occurance

all: cli

$(BUILD):
	mkdir -p $(BUILD)

# cli search application
$(BUILD)/search_cli: $(ROOT)/cli/main.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(OPS)/PostingsOperations.cpp $(TRIE)/trie.cpp $(PARSER)/query_parser.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) -I$(OPS) -I$(TRIE) $^ -o $@

cli: $(BUILD)/search_cli

run: cli
	./$(BUILD)/search_cli $(CORPUS)

$(BUILD)/storetime: $(W2)/store_time.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(ROOT)/wl2/lib/src/include $^ -o $@

storetime: $(BUILD)/storetime
	./$(BUILD)/storetime

$(BUILD)/occurance: $(W2)/occurance.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(ROOT)/wl2/lib/src/include $^ -o $@

occurance: $(BUILD)/occurance
	./$(BUILD)/occurance

# Worklet 3 bridge test
$(BUILD)/bridge_test: $(ROOT)/tests/wl2/Worklet3BridgeTest.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(OPS)/PostingsOperations.cpp $(TRIE)/trie.cpp $(PARSER)/query_parser.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) -I$(OPS) -I$(TRIE) $^ -o $@

# Posting operations tests
$(BUILD)/postings_test: $(ROOT)/tests/wl2/QueryPostingsOperationsTest.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Posting operations extended tests (14 test cases)
$(BUILD)/postings_ops_test: $(ROOT)/tests/wl2/PostingsOperationsTest.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Posting operations benchmark
$(BUILD)/postings_benchmark: $(ROOT)/tests/wl2/PostingsOperationsBenchmark.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Quick union benchmark (small inputs) using the production functions.
$(BUILD)/union_skip_small: $(ROOT)/tests/wl2/UnionSkipComparisonDemo.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -DSMALL_BENCHMARK -I$(W2) -I$(OPS) $^ -o $@

benchmark-union-small: $(BUILD)/union_skip_small
	./$(BUILD)/union_skip_small

# Broader union benchmark (large inputs) using the production functions.
$(BUILD)/union_skip_big: $(ROOT)/tests/wl2/UnionSkipBenchmark.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

benchmark-union-big: $(BUILD)/union_skip_big
	./$(BUILD)/union_skip_big

# Compare the fixed skip intervals, along with adaptive and exponential skips.
$(BUILD)/skip_offset_benchmark: $(ROOT)/tests/wl2/PostingsOperationsBenchmark.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

benchmark-skip-offsets: $(BUILD)/skip_offset_benchmark
	./$(BUILD)/skip_offset_benchmark

# Trie tests
$(BUILD)/trie_test: $(TRIE)/trietests.cpp $(TRIE)/trie.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(TRIE) $^ -o $@

# Trie wildcard demo over the loaded corpus, with lemmatized outputs.
$(BUILD)/trie_demo: $(ROOT)/tests/wl2/TrieDemo.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(OPS)/PostingsOperations.cpp $(TRIE)/trie.cpp $(PARSER)/query_parser.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) -I$(OPS) -I$(TRIE) $^ -o $@

trie: $(BUILD)/trie_demo
	./$(BUILD)/trie_demo $(CORPUS)

# Small lemmatization demo to show several inflected forms collapsing to one lemma.
$(BUILD)/lemma_demo: $(ROOT)/tests/wl2/LemmaDemo.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(ROOT)/wl2/lib/src/include $^ -o $@

lemma: $(BUILD)/lemma_demo
	./$(BUILD)/lemma_demo

test-boolean: $(BUILD)/postings_test $(BUILD)/postings_ops_test $(BUILD)/bridge_test
	@echo "Boolean Operations Unit Tests (randomized)"
	./$(BUILD)/postings_test
	@echo ""
	@echo "Boolean Operations Extended Tests (14 cases)"
	./$(BUILD)/postings_ops_test
	@echo ""
	@echo "Boolean Query Integration Tests "
	./$(BUILD)/bridge_test
	@echo ""
	@echo "All Boolean tests passed"

test-wl2: $(BUILD)/bridge_test $(BUILD)/postings_test $(BUILD)/postings_ops_test $(BUILD)/trie_test
	./$(BUILD)/bridge_test
	./$(BUILD)/postings_test
	./$(BUILD)/postings_ops_test
	./$(BUILD)/trie_test

test: test-wl2

# Python bindings for wl3
pybind:
	@PYBIND_INCLUDES="$$(python3 -m pybind11 --includes 2>/dev/null)"; \
	if [ -z "$$PYBIND_INCLUDES" ]; then \
		echo 'pybind11 is required: python3 -m pip install pybind11'; \
		exit 2; \
	fi; \
	mkdir -p $(BUILD); \
	$(CXX) $(CXXFLAGS) -shared -fPIC $$PYBIND_INCLUDES \
		-I$(W2) -I$(PARSER) \
		-I$(OPS) -I$(TRIE) \
		$(PARSER)/python_bindings.cpp \
		$(W2)/CorpusReader.cpp \
		$(W2)/HashMap.cpp \
		$(W2)/Posting.cpp \
		$(W2)/Inverted_Index.cpp \
		$(OPS)/PostingsOperations.cpp \
		$(TRIE)/trie.cpp \
		$(PARSER)/query_parser.cpp \
		$(TEXT) \
		-o $(BUILD)/wl2bridge$$(python3-config --extension-suffix)

clean:
	rm -rf $(BUILD)
