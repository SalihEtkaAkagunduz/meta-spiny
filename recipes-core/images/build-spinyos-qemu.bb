SUMMARY = "SpinyOS QEMU Test Image"
DESCRIPTION = "QEMU-friendly SpinyOS image for full-stack validation on non-RPi hosts"
LICENSE = "MIT"

inherit core-image

IMAGE_FEATURES += "ssh-server-openssh debug-tweaks"
IMAGE_FEATURES += "package-management"
IMAGE_FEATURES:remove = "splash"

set_root_password() {
    sed -i 's|^root::|root:$1$ACWa9SQV$yBidCPmBB6tt0YfgNE6KO1:|' ${IMAGE_ROOTFS}/etc/shadow
}

set_hostname() {
    echo "spinyos-qemu" > ${IMAGE_ROOTFS}/etc/hostname
}

IMAGE_INSTALL:append = " \
    python3-core python3-requests python3-modules \
    chrony connman-wait-online resize-rootfs parted e2fsprogs-resize2fs \
    util-linux coreutils procps bash neofetch \
    openssh openssh-sftp-server openssh-scp \
    system-health spinyctl spiny-orchestrator \
    ros-core rclpy rclcpp std-msgs sensor-msgs geometry-msgs diagnostic-msgs \
    rclcpp-lifecycle launch-ros ros2cli ros2launch ros2cli-common-extensions \
    ros2node ros2topic ros2service ros2param ros2lifecycle ros2action \
    demo-nodes-cpp rmw-fastrtps-cpp ros2-runtime-config \
"

# QEMU profile intentionally excludes Raspberry Pi specific firmware/drivers and AP stack
# to keep virtualization runs stable and hardware-agnostic.

configure_sshd() {
    if [ -f ${IMAGE_ROOTFS}/etc/ssh/sshd_config ]; then
        sed -i 's|^#PermitRootLogin .*|PermitRootLogin yes|' ${IMAGE_ROOTFS}/etc/ssh/sshd_config
        sed -i 's|^#PasswordAuthentication .*|PasswordAuthentication yes|' ${IMAGE_ROOTFS}/etc/ssh/sshd_config
    fi
}

enable_sshd() {
    if [ -d ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants ]; then
        ln -sf /lib/systemd/system/sshd.socket ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/sshd.socket
    fi
}

ROOTFS_POSTPROCESS_COMMAND += "set_root_password; set_hostname; configure_sshd; enable_sshd;"
