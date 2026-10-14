CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2

SRCDIR = Pos_Inverted_Index
OPSDIR = boolean_operations
TESTDIR = ../tests/wl2

SRC_FILES = $(SRCDIR)/HashMap.cpp $(SRCDIR)/JsonReader.cpp
MAIN_FILE = $(SRCDIR)/main.cpp
POSTINGS_OPS_SRC = $(OPSDIR)/PostingsOperations.cpp

TEST_SRC = $(TESTDIR)/PostingsOperationsTest.cpp

.PHONY: all test asan clean

all: main

main: $(MAIN_FILE) $(SRC_FILES)
	$(CXX) $(CXXFLAGS) -I$(SRCDIR) $^ -o $(SRCDIR)/index_engine

test: $(TEST_SRC) $(POSTINGS_OPS_SRC)
	$(CXX) $(CXXFLAGS) -I$(OPSDIR) $^ -o $(TESTDIR)/test_runner
	./$(TESTDIR)/test_runner

asan: $(TEST_SRC) $(POSTINGS_OPS_SRC)
	$(CXX) -std=c++17 -Wall -Wextra -g -fsanitize=address,undefined -I$(OPSDIR) $^ -o $(TESTDIR)/test_runner_asan
	./$(TESTDIR)/test_runner_asan

clean:
	rm -f $(SRCDIR)/index_engine $(TESTDIR)/test_runner $(TESTDIR)/test_runner_asan
