SUMMARY = "Framebuffer copy tool for Raspberry Pi"
DESCRIPTION = "Tool to copy primary framebuffer to secondary framebuffer (e.g., HDMI to SPI LCD)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://fbcp.c \
           file://CMakeLists.txt"

S = "${WORKDIR}"

inherit cmake

# No dependencies needed - pure Linux framebuffer API

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/fbcp ${D}${bindir}/
}

FILES:${PN} = "${bindir}/fbcp"

COMPATIBLE_MACHINE = "^rpi$"
