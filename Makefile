CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2

ROOT := .
BUILD := $(ROOT)/build

W2 := wl2/Inverted_Index
OPS := wl2/boolean_operations
PARSER := wl2/Pos_Inverted_Index
TEXT := wl2/lib/src/libfreeling/text_processing.cc
TRIE := wl2/trie

.PHONY: all cli test test-wl2 run clean pybind

all: cli

$(BUILD):
	mkdir -p $(BUILD)

# cli search application
$(BUILD)/search_cli: $(ROOT)/cli/main.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(OPS)/PostingsOperations.cpp $(TRIE)/trie.cpp $(PARSER)/query_parser.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) -I$(OPS) -I$(TRIE) $^ -o $@

cli: $(BUILD)/search_cli

run: cli
	./$(BUILD)/search_cli $(CORPUS)

# Worklet 3 bridge test
$(BUILD)/bridge_test: $(ROOT)/tests/wl2/Worklet3BridgeTest.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(W2)/Inverted_Index.cpp $(OPS)/PostingsOperations.cpp $(TRIE)/trie.cpp $(PARSER)/query_parser.cpp $(TEXT) | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) -I$(OPS) -I$(TRIE) $^ -o $@

# Posting operations tests
$(BUILD)/postings_test: $(ROOT)/tests/wl2/QueryPostingsOperationsTest.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Posting operations benchmark
$(BUILD)/postings_benchmark: $(ROOT)/tests/wl2/PostingsOperationsBenchmark.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Trie tests
$(BUILD)/trie_test: $(TRIE)/trietests.cpp $(TRIE)/trie.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(TRIE) $^ -o $@

test-wl2: $(BUILD)/bridge_test $(BUILD)/postings_test $(BUILD)/trie_test
	./$(BUILD)/bridge_test
	./$(BUILD)/postings_test
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
