# Storage Optimization Makefile

CC := gcc
CFLAGS := -Wall -Wextra -O3 -march=native -I./include
LDFLAGS := -lrt -lpthread

SRC_DIR := src
INC_DIR := include
BUILD_DIR := build
TEST_DIR := tests
BENCH_DIR := benchmarks

# Source files
SRCS := $(wildcard $(SRC_DIR)/*.c)
OBJS := $(SRCS:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)

# Target library
TARGET_LIB := $(BUILD_DIR)/libstorage.a
TARGET_SO := $(BUILD_DIR)/libstorage.so

# Test programs
TESTS := $(BUILD_DIR)/test_storage
BENCHMARKS := $(BUILD_DIR)/benchmark_storage

.PHONY: all clean install test benchmark

all: $(TARGET_LIB) $(TARGET_SO)

# Static library
$(TARGET_LIB): $(OBJS)
	@mkdir -p $(BUILD_DIR)
	ar rcs $@ $^
	@echo "Built static library: $@"

# Shared library
$(TARGET_SO): $(OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) -shared -o $@ $^ $(LDFLAGS)
	@echo "Built shared library: $@"

# Object files
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -fPIC -c $< -o $@

# Tests
test: $(TESTS)
	@echo "Running storage tests..."
	$(TESTS)

$(TESTS): $(TEST_DIR)/test_storage.c $(TARGET_LIB)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< -L$(BUILD_DIR) -lstorage $(LDFLAGS)

# Benchmarks
benchmark: $(BENCHMARKS)
	@echo "Running storage benchmarks..."
	sudo $(BENCHMARKS)

$(BENCHMARKS): $(BENCH_DIR)/benchmark.c $(TARGET_LIB)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< -L$(BUILD_DIR) -lstorage $(LDFLAGS)

# Install
install: $(TARGET_LIB) $(TARGET_SO)
	@echo "Installing storage library..."
	sudo mkdir -p /usr/local/lib
	sudo mkdir -p /usr/local/include/footballvision
	sudo cp $(TARGET_LIB) /usr/local/lib/
	sudo cp $(TARGET_SO) /usr/local/lib/
	sudo cp $(INC_DIR)/*.h /usr/local/include/footballvision/
	sudo ldconfig
	@echo "Installation complete"

# Clean
clean:
	rm -rf $(BUILD_DIR)
	@echo "Clean complete"

# Help
help:
	@echo "Storage Optimization Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all        - Build libraries (default)"
	@echo "  test       - Build and run tests"
	@echo "  benchmark  - Build and run benchmarks"
	@echo "  install    - Install libraries and headers"
	@echo "  clean      - Remove build artifacts"
	@echo "  help       - Show this message"