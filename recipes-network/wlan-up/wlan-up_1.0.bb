SUMMARY = "Bring up wlan0 interface at boot"
DESCRIPTION = "Simple service that runs `ifconfig wlan0 up` during system boot to ensure the wireless interface is enabled."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://wlan-up.sh \
           file://wlan-up.service \
           file://wpa_supplicant-wlan0.conf \
           file://wlan-up.tmpfiles"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "wlan-up.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    # install the script to /usr/bin so systemd can execute it directly
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/wlan-up.sh ${D}${bindir}/wlan-up.sh
    # install the systemd unit file
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/wlan-up.service ${D}${systemd_unitdir}/system/wlan-up.service
    # install tmpfiles config
    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 0644 ${WORKDIR}/wlan-up.tmpfiles ${D}${sysconfdir}/tmpfiles.d/wlan-up.conf
}

# Ship the installed script, tmpfiles config and the systemd unit
FILES:${PN} += "${bindir}/wlan-up.sh ${sysconfdir}/tmpfiles.d/wlan-up.conf ${systemd_unitdir}/system/wlan-up.service"

# runtime dependencies: wpa_supplicant for WiFi and net-tools for ifconfig
RDEPENDS:${PN} += "wpa-supplicant"
# /usr/root/log.txt is created by systemd-tmpfiles at boot; do not ship a static file to avoid QA errors
