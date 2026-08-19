SUMMARY = "Nokia 5110 LCD Display Application - Alternative Version"
DESCRIPTION = "Nokia 5110 (PCD8544) LCD display driver and applications for Raspberry Pi - Uses SPI1 to avoid conflicts"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://nokia5110_driver_alt.py \
    file://nokia5110-demo.py \
    file://nokia5110-monitor.py \
    file://nokia5110-text.py \
    file://README-NOKIA5110.md \
    file://HIZLI-BASLANGIC.md \
"

S = "${WORKDIR}"

# Dependencies
RDEPENDS:${PN} = " \
    python3-core \
    python3-spidev \
    python3-periphery \
    rpi-gpio \
"

do_install() {
    # Install Python driver and applications
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/nokia5110_driver_alt.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/nokia5110-demo.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/nokia5110-monitor.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/nokia5110-text.py ${D}${bindir}/
    
    # Install documentation
    install -d ${D}${docdir}/${PN}
    install -m 0644 ${WORKDIR}/README-NOKIA5110.md ${D}${docdir}/${PN}/
    install -m 0644 ${WORKDIR}/HIZLI-BASLANGIC.md ${D}${docdir}/${PN}/
}

FILES:${PN} += " \
    ${bindir}/nokia5110_driver_alt.py \
    ${bindir}/nokia5110-demo.py \
    ${bindir}/nokia5110-monitor.py \
    ${bindir}/nokia5110-text.py \
    ${docdir}/${PN}/README-NOKIA5110.md \
    ${docdir}/${PN}/HIZLI-BASLANGIC.md \
"