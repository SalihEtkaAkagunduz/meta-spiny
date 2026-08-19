SUMMARY = "SpinyOS WiFi Manager"
DESCRIPTION = "State-machine based WiFi manager: AP provisioning mode with fallback, \
               client mode with saved credentials, mDNS hostname advertisement."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://wifi-manager.sh \
           file://wifi-manager.service \
           file://wifi-provision-server.py \
           file://wifi-ready-notifier.py \
           file://wifi-state"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "wifi-manager.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    # Main state machine script
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/wifi-manager.sh      ${D}${bindir}/wifi-manager.sh
    install -m 0755 ${WORKDIR}/wifi-provision-server.py ${D}${bindir}/wifi-provision-server.py
    install -m 0755 ${WORKDIR}/wifi-ready-notifier.py ${D}${bindir}/wifi-ready-notifier.py

    # Systemd unit
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/wifi-manager.service \
                    ${D}${systemd_unitdir}/system/wifi-manager.service

    # Initial state file — device starts in unconfigured / AP mode
    install -d ${D}${sysconfdir}/spiny
    install -m 0600 ${WORKDIR}/wifi-state ${D}${sysconfdir}/spiny/wifi-state
}

FILES:${PN} += " \
    ${bindir}/wifi-manager.sh \
    ${bindir}/wifi-provision-server.py \
    ${bindir}/wifi-ready-notifier.py \
    ${sysconfdir}/spiny/wifi-state \
    ${systemd_unitdir}/system/wifi-manager.service \
"

# Runtime deps: wpa_supplicant, hostapd (AP mode), dnsmasq (DHCP for AP clients),
# avahi-daemon (mDNS .local hostname), python3 (provisioning HTTP server)
RDEPENDS:${PN} += " \
    wpa-supplicant \
    hostapd \
    dnsmasq \
    avahi-daemon \
    python3-core \
"
