#!/bin/bash
# JetPack 6.0 Custom Image Builder
# Builds optimized system image for FootballVision Pro

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/image-config.yaml"
WORK_DIR="${SCRIPT_DIR}/../build"
IMAGE_NAME="footballvision-jetson-1.0.0"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    local deps=(
        "qemu-user-static"
        "binfmt-support"
        "debootstrap"
        "parted"
        "kpartx"
        "wget"
        "tar"
        "python3"
        "pyyaml"
    )

    for dep in "${deps[@]}"; do
        if ! dpkg -l | grep -q "^ii.*${dep}"; then
            log_error "Missing dependency: ${dep}"
            log_info "Install with: sudo apt-get install ${dep}"
            exit 1
        fi
    done

    log_success "All dependencies satisfied"
}

download_jetpack() {
    log_info "Downloading JetPack 6.0 base..."

    local JETPACK_URL="https://developer.nvidia.com/downloads/jetpack-60-orin-nano-super"
    local JETPACK_FILE="${WORK_DIR}/jetpack-6.0-base.tar.gz"

    mkdir -p "${WORK_DIR}"

    if [ ! -f "${JETPACK_FILE}" ]; then
        log_info "Downloading from ${JETPACK_URL}"
        wget -O "${JETPACK_FILE}" "${JETPACK_URL}" || {
            log_error "Failed to download JetPack"
            log_info "Please download manually from NVIDIA Developer Portal"
            exit 1
        }
    else
        log_info "Using cached JetPack base"
    fi

    log_success "JetPack base ready"
}

extract_base() {
    log_info "Extracting base filesystem..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"

    if [ -d "${ROOTFS_DIR}" ]; then
        log_warning "Removing existing rootfs"
        sudo rm -rf "${ROOTFS_DIR}"
    fi

    mkdir -p "${ROOTFS_DIR}"

    sudo tar -xzf "${WORK_DIR}/jetpack-6.0-base.tar.gz" -C "${ROOTFS_DIR}"

    log_success "Base filesystem extracted"
}

setup_chroot() {
    log_info "Setting up chroot environment..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"

    # Mount proc, sys, dev
    sudo mount -t proc /proc "${ROOTFS_DIR}/proc"
    sudo mount -t sysfs /sys "${ROOTFS_DIR}/sys"
    sudo mount -o bind /dev "${ROOTFS_DIR}/dev"
    sudo mount -o bind /dev/pts "${ROOTFS_DIR}/dev/pts"

    # Copy qemu for ARM emulation
    sudo cp /usr/bin/qemu-aarch64-static "${ROOTFS_DIR}/usr/bin/"

    # Copy DNS
    sudo cp /etc/resolv.conf "${ROOTFS_DIR}/etc/resolv.conf"

    log_success "Chroot environment ready"
}

cleanup_chroot() {
    log_info "Cleaning up chroot..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"

    # Unmount in reverse order
    sudo umount "${ROOTFS_DIR}/dev/pts" 2>/dev/null || true
    sudo umount "${ROOTFS_DIR}/dev" 2>/dev/null || true
    sudo umount "${ROOTFS_DIR}/sys" 2>/dev/null || true
    sudo umount "${ROOTFS_DIR}/proc" 2>/dev/null || true

    log_success "Chroot cleaned up"
}

install_packages() {
    log_info "Installing system packages..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"

    # Create package installation script
    cat > "${WORK_DIR}/install_packages.sh" << 'EOF'
#!/bin/bash
set -e

# Update package lists
apt-get update

# Install development tools
apt-get install -y build-essential cmake git python3-dev python3-pip \
    device-tree-compiler linux-headers-generic

# Install video utilities
apt-get install -y v4l-utils ffmpeg gstreamer1.0-tools \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Install system utilities
apt-get install -y htop iotop sysstat nvme-cli smartmontools \
    lm-sensors i2c-tools

# Install network utilities
apt-get install -y net-tools iproute2 iperf3 tcpdump ethtool

# Remove unnecessary packages
apt-get purge -y libreoffice* thunderbird* rhythmbox* shotwell* \
    gnome-games* 2>/dev/null || true

# Clean up
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/*
EOF

    chmod +x "${WORK_DIR}/install_packages.sh"
    sudo cp "${WORK_DIR}/install_packages.sh" "${ROOTFS_DIR}/tmp/"
    sudo chroot "${ROOTFS_DIR}" /tmp/install_packages.sh

    log_success "Packages installed"
}

install_nvidia_components() {
    log_info "Installing NVIDIA components..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"

    cat > "${WORK_DIR}/install_nvidia.sh" << 'EOF'
#!/bin/bash
set -e

# Add NVIDIA repository
wget https://repo.download.nvidia.com/jetson/jetson-ota-public.asc -O /etc/apt/trusted.gpg.d/jetson-ota-public.asc
echo "deb https://repo.download.nvidia.com/jetson/common r36.2 main" > /etc/apt/sources.list.d/nvidia-l4t-apt-source.list

apt-get update

# Install CUDA
apt-get install -y cuda-toolkit-12-2 cuda-libraries-12-2 \
    cuda-runtime-12-2 cuda-command-line-tools-12-2

# Install cuDNN
apt-get install -y libcudnn8 libcudnn8-dev

# Install TensorRT
apt-get install -y tensorrt python3-libnvinfer python3-libnvinfer-dev

# Install VPI
apt-get install -y libnvvpi3 vpi3-dev

# Install multimedia components
apt-get install -y nvidia-l4t-multimedia nvidia-l4t-multimedia-utils \
    nvidia-l4t-camera nvidia-l4t-gstreamer \
    nvidia-l4t-jetson-multimedia-api nvidia-l4t-3d-core

apt-get clean
EOF

    chmod +x "${WORK_DIR}/install_nvidia.sh"
    sudo cp "${WORK_DIR}/install_nvidia.sh" "${ROOTFS_DIR}/tmp/"
    sudo chroot "${ROOTFS_DIR}" /tmp/install_nvidia.sh

    log_success "NVIDIA components installed"
}

configure_kernel() {
    log_info "Configuring kernel parameters..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"
    local CMDLINE="quiet splash=0 console=ttyTCU0,115200 isolcpus=1,2,3,4,5 nohz_full=1,2,3,4,5 rcu_nocbs=1,2,3,4,5 irqaffinity=0"

    # Update boot configuration
    echo "${CMDLINE}" | sudo tee "${ROOTFS_DIR}/boot/extlinux/extlinux.conf.cmdline"

    log_success "Kernel configured"
}

optimize_system() {
    log_info "Applying system optimizations..."

    local ROOTFS_DIR="${WORK_DIR}/rootfs"

    # Sysctl optimizations
    sudo tee "${ROOTFS_DIR}/etc/sysctl.d/99-footballvision.conf" > /dev/null << EOF
# VM optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# Network optimizations
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.ipv4.tcp_rmem = 4096 87380 268435456
net.ipv4.tcp_wmem = 4096 65536 268435456

# File system
fs.file-max = 1000000
fs.inotify.max_user_watches = 524288

# Disable IPv6
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
EOF

    # I/O scheduler
    sudo tee "${ROOTFS_DIR}/etc/udev/rules.d/60-ioschedulers.rules" > /dev/null << EOF
# Set I/O scheduler for NVMe
ACTION=="add|change", KERNEL=="nvme[0-9]n[0-9]", ATTR{queue/scheduler}="none"

# Set I/O scheduler for SD cards
ACTION=="add|change", KERNEL=="mmcblk[0-9]", ATTR{queue/scheduler}="mq-deadline"
EOF

    log_success "System optimized"
}

create_image() {
    log_info "Creating system image..."

    local IMAGE_FILE="${WORK_DIR}/${IMAGE_NAME}.img"
    local IMAGE_SIZE="20G"

    # Create sparse image
    dd if=/dev/zero of="${IMAGE_FILE}" bs=1 count=0 seek="${IMAGE_SIZE}"

    # Partition the image
    parted "${IMAGE_FILE}" mklabel gpt
    parted "${IMAGE_FILE}" mkpart primary ext4 0% 100%

    # Setup loop device
    local LOOP_DEV=$(sudo losetup --find --show "${IMAGE_FILE}")
    sudo kpartx -av "${LOOP_DEV}"

    # Format partition
    local PART_DEV="/dev/mapper/$(basename ${LOOP_DEV})p1"
    sudo mkfs.ext4 -F -L "footballvision-rootfs" "${PART_DEV}"

    # Mount and copy rootfs
    local MOUNT_DIR="${WORK_DIR}/mnt"
    mkdir -p "${MOUNT_DIR}"
    sudo mount "${PART_DEV}" "${MOUNT_DIR}"

    sudo rsync -aAXv "${WORK_DIR}/rootfs/" "${MOUNT_DIR}/"

    # Unmount and cleanup
    sudo umount "${MOUNT_DIR}"
    sudo kpartx -dv "${LOOP_DEV}"
    sudo losetup -d "${LOOP_DEV}"

    # Compress image
    log_info "Compressing image..."
    gzip -9 "${IMAGE_FILE}"

    log_success "Image created: ${IMAGE_FILE}.gz"
}

main() {
    echo "=========================================="
    echo "  FootballVision JetPack Image Builder"
    echo "=========================================="
    echo ""

    if [ "$EUID" -ne 0 ]; then
        log_warning "This script requires root privileges for some operations"
    fi

    check_dependencies
    download_jetpack
    extract_base
    setup_chroot

    trap cleanup_chroot EXIT

    install_packages
    install_nvidia_components
    configure_kernel
    optimize_system

    cleanup_chroot
    trap - EXIT

    create_image

    echo ""
    log_success "Build complete!"
    echo ""
    echo "Flash image with:"
    echo "  sudo ./flash-jetson.sh ${WORK_DIR}/${IMAGE_NAME}.img.gz"
    echo ""
}

main "$@"