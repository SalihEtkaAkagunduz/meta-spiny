SUMMARY = "SpinyOS ROS2 runtime shell environment"
DESCRIPTION = "Adds profile.d script to source ROS2 workspace and set default RMW/domain settings"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://ros2-runtime-env.sh"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${sysconfdir}/profile.d
    install -m 0644 ${WORKDIR}/ros2-runtime-env.sh ${D}${sysconfdir}/profile.d/ros2-runtime-env.sh
}

FILES:${PN} += "${sysconfdir}/profile.d/ros2-runtime-env.sh"
