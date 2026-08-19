SUMMARY = "Device metrics ingest client"
DESCRIPTION = "Simple Python service that POSTs device metrics to a remote HTTPS endpoint periodically"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://device-ingest.py file://device-ingest.service file://device-ingest.tmpfiles file://telemetry.py"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "device-ingest.service"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/device-ingest.py ${D}${bindir}/device-ingest.py
    install -m 0755 ${WORKDIR}/telemetry.py ${D}${bindir}/telemetry

    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/device-ingest.service ${D}${systemd_unitdir}/system/device-ingest.service

    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 0644 ${WORKDIR}/device-ingest.tmpfiles ${D}${sysconfdir}/tmpfiles.d/device-ingest.conf
}

FILES:${PN} += "${bindir}/device-ingest.py ${bindir}/telemetry ${systemd_unitdir} ${systemd_unitdir}/system ${systemd_unitdir}/system/device-ingest.service ${sysconfdir}/tmpfiles.d/device-ingest.conf"

RDEPENDS_${PN} += "python3 python3-requests"

SYSTEMD_AUTO_ENABLE:${PN} = "enable"
