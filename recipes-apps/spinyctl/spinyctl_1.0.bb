SUMMARY = "SpinyOS control CLI"
DESCRIPTION = "JSON-friendly control CLI for device info, Wi-Fi status, service control, and custom command dispatch"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://spinyctl.py"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/spinyctl.py ${D}${bindir}/spinyctl

    install -d ${D}${libexecdir}/spinyctl/commands
}

FILES:${PN} += " \
    ${bindir}/spinyctl \
    ${libexecdir}/spinyctl/commands \
"

RDEPENDS:${PN} += " \
    python3-core \
    python3-websockets \
"