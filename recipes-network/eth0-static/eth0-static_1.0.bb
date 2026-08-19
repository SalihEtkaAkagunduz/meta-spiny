SUMMARY = "Static eth0 address for direct cable use"
DESCRIPTION = "Assigns 192.168.50.2/24 to eth0 at boot so the host app can reach SpinyOS over direct Ethernet"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://eth0-static.sh \
           file://eth0-static.service \
           file://eth0-dhcp.service \
           file://eth0-dnsmasq.conf"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "eth0-static.service eth0-dhcp.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/eth0-static.sh ${D}${bindir}/eth0-static.sh

    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/eth0-static.service \
        ${D}${systemd_unitdir}/system/eth0-static.service
    install -m 0644 ${WORKDIR}/eth0-dhcp.service \
        ${D}${systemd_unitdir}/system/eth0-dhcp.service

    install -d ${D}${sysconfdir}/spiny
    install -m 0644 ${WORKDIR}/eth0-dnsmasq.conf \
        ${D}${sysconfdir}/spiny/eth0-dnsmasq.conf
}

FILES:${PN} += " \
    ${bindir}/eth0-static.sh \
    ${systemd_unitdir}/system/eth0-static.service \
    ${systemd_unitdir}/system/eth0-dhcp.service \
    ${sysconfdir}/spiny/eth0-dnsmasq.conf \
"

RDEPENDS:${PN} += "iproute2 dnsmasq"