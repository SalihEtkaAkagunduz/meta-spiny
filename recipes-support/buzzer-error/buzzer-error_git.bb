SUMMARY = "Buzzer Error Service"
DESCRIPTION = "A service to control buzzer on GPIO pin for error notifications"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=5ca89be1b2aeb4f30d716ffe88170f83"

SRC_URI += " \
    file://buzzer-error.sh \
    file://buzzer-error.service \
    file://buzzer-pin.conf \
    file://buzzererror \
    file://LICENSE \
"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${sbindir}
    install -m 0755 ${WORKDIR}/buzzer-error.sh ${D}${sbindir}/

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/buzzer-error.service ${D}${systemd_system_unitdir}/
  
    install -d ${D}${sysconfdir}
    install -m 0644 ${WORKDIR}/buzzer-pin.conf ${D}${sysconfdir}/

    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/buzzererror ${D}${bindir}/

    install -d ${D}${datadir}/licenses/${PN}
    install -m 0644 ${WORKDIR}/LICENSE ${D}${datadir}/licenses/${PN}/
}

SYSTEMD_SERVICE:${PN} = "buzzer-error.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

FILES:${PN} = " \
    ${sbindir}/buzzer-error.sh \
    ${systemd_system_unitdir}/buzzer-error.service \
    ${sysconfdir}/buzzer-pin.conf \
    ${bindir}/buzzererror \
    ${datadir}/licenses/${PN}/LICENSE \
"

RDEPENDS:${PN} = "bash"