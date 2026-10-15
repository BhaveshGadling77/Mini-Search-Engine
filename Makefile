CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2
BUILD := build
W2 := wl2/Inverted_Index
OPS := wl2/boolean_operations
PARSER := wl2/Pos_Inverted_Index

.PHONY: all cli test test-wl2 run clean pybind
all: cli
$(BUILD):
	mkdir -p $(BUILD)
$(BUILD)/search_cli: cli/main.cpp $(W2)/CorpusReader.cpp $(W2)/HashMap.cpp $(W2)/Posting.cpp $(PARSER)/query_parser.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) $^ -o $@
cli: $(BUILD)/search_cli
run: cli
	./$(BUILD)/search_cli $(CORPUS)
$(BUILD)/bridge_test: tests/wl2/Worklet3BridgeTest.cpp $(W2)/CorpusReader.cpp $(PARSER)/query_parser.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(PARSER) $^ -o $@
$(BUILD)/postings_test: tests/wl2/QueryPostingsOperationsTest.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@
$(BUILD)/postings_benchmark: tests/wl2/PostingsOperationsBenchmark.cpp $(OPS)/PostingsOperations.cpp $(W2)/Posting.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(W2) -I$(OPS) $^ -o $@
$(BUILD)/trie_test: wl2/trie/trietests.cpp wl2/trie/trie.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -Iwl2/trie $^ -o $@
test-wl2: $(BUILD)/bridge_test $(BUILD)/postings_test $(BUILD)/trie_test
	./$(BUILD)/bridge_test
	./$(BUILD)/postings_test
	./$(BUILD)/trie_test
test: test-wl2
pybind:
	@PYBIND_INCLUDES="$$(python3 -m pybind11 --includes 2>/dev/null)"; \
	if [ -z "$$PYBIND_INCLUDES" ]; then echo 'pybind11 is required: python3 -m pip install pybind11'; exit 2; fi; \
	mkdir -p $(BUILD); \
	$(CXX) $(CXXFLAGS) -shared -fPIC $$PYBIND_INCLUDES -I$(W2) -I$(PARSER) $(PARSER)/python_bindings.cpp $(W2)/CorpusReader.cpp $(PARSER)/query_parser.cpp -o $(BUILD)/w2bridge$$(python3-config --extension-suffix)
clean:
	rm -rf $(BUILD)
