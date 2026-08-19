SUMMARY = "Nokia 5110 SPI enabler"
DESCRIPTION = "Ensures SPI is enabled in /boot/config.txt for Nokia 5110"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://enable-nokia-spi.sh \
    file://nokia-spi-enabler.service \
"

S = "${WORKDIR}"

RDEPENDS:${PN} = "bash"

inherit systemd

SYSTEMD_SERVICE:${PN} = "nokia-spi-enabler.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    install -d ${D}${sbindir}
    install -m 0755 ${WORKDIR}/enable-nokia-spi.sh ${D}${sbindir}/
    
    # Install systemd service
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/nokia-spi-enabler.service ${D}${systemd_unitdir}/system/
}

FILES:${PN} += " \
    ${sbindir}/enable-nokia-spi.sh \
    ${systemd_unitdir}/system/nokia-spi-enabler.service \
"
