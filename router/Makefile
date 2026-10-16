CXX ?= g++
CXXFLAGS ?= -O2 -std=c++20 -Wall -Wextra -ffp-contract=off -pthread
BUILD := build

$(BUILD)/m3d_route: src/main.cpp src/json.hpp
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ src/main.cpp

.PHONY: test clean
test: $(BUILD)/m3d_route
	bash tests/run_tests.sh

clean:
	rm -rf $(BUILD)
