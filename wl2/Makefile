CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2

ROOT := ..
BUILD := $(ROOT)/build

W2 := Inverted_Index
OPS := boolean_operations
PARSER := Pos_Inverted_Index

.PHONY: all cli test test-wl2 run clean pybind

all: cli

$(BUILD):
	mkdir -p $(BUILD)

# cli search application
$(BUILD)/search_cli: $(ROOT)/cli/main.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(PARSER)/query_parser.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) $^ -o $@

cli: $(BUILD)/search_cli

run: cli
	./$(BUILD)/search_cli $(CORPUS)

# Worklet 3 bridge test
$(BUILD)/bridge_test: $(ROOT)/tests/wl2/Worklet3BridgeTest.cpp $(W2)/CorpusReader.cpp $(PARSER)/query_parser.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) $^ -o $@

# Posting operations tests
$(BUILD)/postings_test: $(ROOT)/tests/wl2/QueryPostingsOperationsTest.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Posting operations benchmark
$(BUILD)/postings_benchmark: $(ROOT)/tests/wl2/PostingsOperationsBenchmark.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@

# Trie tests
$(BUILD)/trie_test: trie/trietests.cpp trie/trie.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -Itrie $^ -o $@

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
		$(PARSER)/python_bindings.cpp \
		$(W2)/CorpusReader.cpp \
		$(PARSER)/query_parser.cpp \
		-o $(BUILD)/wl2bridge$$(python3-config --extension-suffix)

clean:
	rm -rf $(BUILD)