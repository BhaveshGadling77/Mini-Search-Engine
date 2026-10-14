CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2

BUILD_DIR := build
INDEX_DIR := Inverted_Index
OPS_DIR := boolean_operations
TEST_DIR := ../tests/wl2

INDEX_SOURCES := \
	$(INDEX_DIR)/main.cpp \
	$(INDEX_DIR)/CorpusReader.cpp \
	$(INDEX_DIR)/HashMap.cpp \
	$(INDEX_DIR)/Posting.cpp

QUERY_TEST_SOURCES := \
	$(TEST_DIR)/QueryPostingsOperationsTest.cpp \
	$(OPS_DIR)/PostingsOperations.cpp \
	$(INDEX_DIR)/Posting.cpp

.PHONY: all index run test clean

all: test

index: $(BUILD_DIR)/index_engine

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/index_engine: $(INDEX_SOURCES) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -I$(INDEX_DIR) $^ -o $@

$(BUILD_DIR)/query_postings_operations_test: $(QUERY_TEST_SOURCES) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -I$(INDEX_DIR) -I$(OPS_DIR) $^ -o $@

run: $(BUILD_DIR)/index_engine
	cd $(INDEX_DIR) && ../$(BUILD_DIR)/index_engine

test: $(BUILD_DIR)/query_postings_operations_test
	./$(BUILD_DIR)/query_postings_operations_test

clean:
	rm -rf $(BUILD_DIR)
