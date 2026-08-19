SUMMARY = "System Health Check Service"
DESCRIPTION = "Universal system health monitoring service that checks system integrity on boot"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit systemd

SRC_URI = " \
    file://system-health-check.sh \
    file://system-health.service \
"

S = "${WORKDIR}"

SYSTEMD_SERVICE:${PN} = "system-health.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    # Install health check script
    install -d ${D}${sbindir}
    install -m 0755 ${WORKDIR}/system-health-check.sh ${D}${sbindir}/
    
    # Install systemd service
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/system-health.service ${D}${systemd_system_unitdir}/
}

FILES:${PN} = " \
    ${sbindir}/system-health-check.sh \
    ${systemd_system_unitdir}/system-health.service \
"

RDEPENDS:${PN} = "bash"
