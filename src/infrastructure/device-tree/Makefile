# Device Tree Makefile for Dual IMX477 Camera Configuration
# Target: NVIDIA Jetson Orin Nano Super (Tegra234)

DTC := dtc
DTC_FLAGS := -@ -O dtb -o
KERNEL_DIR := /usr/src/linux-headers-$(shell uname -r)

# Source and output files
DTS_SRC := src/tegra234-p3768-camera-imx477-dual.dts
DTB_OUT := tegra234-p3768-camera-imx477-dual.dtbo
INSTALL_DIR := /boot/dtb/overlays

# Include paths for Tegra headers
DTC_INCLUDE := -i $(KERNEL_DIR)/hardware/nvidia/t23x/nv-soc \
               -i $(KERNEL_DIR)/hardware/nvidia/soc/t23x/kernel-include

.PHONY: all clean install uninstall test validate

all: $(DTB_OUT)

# Compile device tree overlay
$(DTB_OUT): $(DTS_SRC)
	@echo "Compiling device tree overlay..."
	$(DTC) $(DTC_FLAGS) $(DTB_OUT) $(DTC_INCLUDE) $(DTS_SRC)
	@echo "Device tree compiled: $(DTB_OUT)"

# Validate device tree syntax
validate: $(DTS_SRC)
	@echo "Validating device tree syntax..."
	$(DTC) -I dts -O dtb $(DTC_INCLUDE) -o /dev/null $(DTS_SRC)
	@echo "Validation passed!"

# Install to system
install: $(DTB_OUT)
	@echo "Installing device tree overlay..."
	@if [ ! -d "$(INSTALL_DIR)" ]; then \
		echo "Creating overlay directory..."; \
		sudo mkdir -p $(INSTALL_DIR); \
	fi
	sudo cp $(DTB_OUT) $(INSTALL_DIR)/
	@echo "Installed to $(INSTALL_DIR)/$(DTB_OUT)"
	@echo ""
	@echo "To enable, add to /boot/extlinux/extlinux.conf:"
	@echo "  FDT /boot/dtb/overlays/$(DTB_OUT)"
	@echo ""
	@echo "Or use jetson-io to select the overlay:"
	@echo "  sudo /opt/nvidia/jetson-io/jetson-io.py"

# Uninstall from system
uninstall:
	@echo "Removing device tree overlay..."
	sudo rm -f $(INSTALL_DIR)/$(DTB_OUT)
	@echo "Uninstalled successfully"

# Decompile for inspection
decompile: $(DTB_OUT)
	@echo "Decompiling device tree..."
	$(DTC) -I dtb -O dts $(DTB_OUT) -o $(DTB_OUT).dts
	@echo "Decompiled to $(DTB_OUT).dts"

# Test camera detection
test:
	@echo "Testing camera detection..."
	@echo "Checking video devices..."
	@ls -l /dev/video* 2>/dev/null || echo "No video devices found"
	@echo ""
	@echo "Checking CSI configuration..."
	@dmesg | grep -i "imx477\|csi\|vi" | tail -20
	@echo ""
	@echo "Checking media controller..."
	@media-ctl -p 2>/dev/null || echo "media-ctl not available"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -f $(DTB_OUT) $(DTB_OUT).dts
	@echo "Clean complete"

# Display help
help:
	@echo "Device Tree Build System for Dual IMX477 Cameras"
	@echo ""
	@echo "Targets:"
	@echo "  all        - Compile device tree overlay (default)"
	@echo "  validate   - Validate device tree syntax"
	@echo "  install    - Install overlay to /boot/dtb/overlays"
	@echo "  uninstall  - Remove overlay from system"
	@echo "  decompile  - Decompile DTB for inspection"
	@echo "  test       - Test camera detection"
	@echo "  clean      - Remove build artifacts"
	@echo "  help       - Show this message"
	@echo ""
	@echo "Requirements:"
	@echo "  - Device Tree Compiler (dtc)"
	@echo "  - Kernel headers installed"
	@echo "  - Root access for installation"