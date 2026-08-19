SUMMARY = "SpinyOS Custom Image"
DESCRIPTION = "A custom image based on core-image-base"
LICENSE = "MIT"

inherit core-image sdcard_image-rpi

# Enable serial and debug features
IMAGE_FEATURES += "ssh-server-openssh debug-tweaks"
IMAGE_FEATURES += "package-management"

# Disable psplash (boot splash screen) to prevent blocking getty
IMAGE_FEATURES:remove = "splash"

# Ensure boot files are deployed before image creation
do_rootfs[depends] += "rpi-config:do_deploy"
do_rootfs[depends] += "nokia-config:do_deploy"
do_rootfs[depends] += "linux-raspberrypi:do_deploy"

set_root_password() {
    sed -i 's|^root::|root:$1$ACWa9SQV$yBidCPmBB6tt0YfgNE6KO1:|' ${IMAGE_ROOTFS}/etc/shadow
}

set_hostname() {
    # Boot-time hostname is set dynamically by the device-identity service
    # (spinyos-<cpu_serial_last8hex>) — only write a placeholder here so that
    # avahi/other services have a valid /etc/hostname before device-identity runs.
    echo "spinyos-00000000" > ${IMAGE_ROOTFS}/etc/hostname
}

IMAGE_INSTALL:append = " python3-core python3-requests python3-modules device-ingest chrony connman-wait-online resize-rootfs parted e2fsprogs-resize2fs util-linux coreutils procps bash neofetch openssh openssh-sftp-server openssh-scp buzzer-error linux-firmware-rpidistro-bcm43455 linux-firmware-overlay nokia5110 nokia-spi-enabler system-health fbcp spinyctl spiny-orchestrator ros-core"
IMAGE_INSTALL:append = " rclpy rclcpp std-msgs sensor-msgs geometry-msgs diagnostic-msgs rclcpp-lifecycle launch-ros ros2cli ros2launch ros2cli-common-extensions ros2node ros2topic ros2service ros2param ros2lifecycle ros2action demo-nodes-cpp rmw-fastrtps-cpp ros2-runtime-config"
IMAGE_INSTALL:append = " curl nano python3-paho-mqtt"
IMAGE_INSTALL:remove = "wlan-up"

# WiFi stack: wifi-manager handles AP provisioning + client mode + AP fallback.
# hostapd     — AP (access-point) mode for provisioning
# dnsmasq     — DHCP server for AP clients during provisioning
# avahi-daemon — mDNS so the device is reachable as <hostname>.local on the LAN
# libnss-mdns — .local resolver for mDNS (resolves *.local on the device too)
# device-identity — generates unique SPINY_DEVICE_ID from CPU serial, sets hostname
IMAGE_INSTALL:append = " wifi-manager hostapd dnsmasq avahi-daemon libnss-mdns device-identity iw eth0-static"

# Display drivers configuration:
# - LCD 3.5" TFT and Nokia 5110 drivers are in recipes-drivers/
# - recipes-bsp/bootfiles/rpi-config_git.bbappend (config.txt modifications)
# - recipes-kernel/linux/linux-raspberrypi_%.bbappend (device tree overlays)
# - recipes-drivers/lcd-touchscreen/ (3.5" LCD touchscreen driver and apps)
# - recipes-drivers/nokia5110/ (Nokia 5110 84x48 LCD driver and apps)

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