FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://lcd35.cfg \
    file://tft35a-overlay.dtb \
    file://ads7846-overlay.dtb \
"

do_deploy:append() {
    # Install Goodtft 3.5" LCD overlays to boot partition
    install -d ${DEPLOYDIR}/bcm2835-bootfiles/overlays
    install -m 0644 ${WORKDIR}/tft35a-overlay.dtb ${DEPLOYDIR}/bcm2835-bootfiles/overlays/tft35a.dtbo
    install -m 0644 ${WORKDIR}/ads7846-overlay.dtb ${DEPLOYDIR}/bcm2835-bootfiles/overlays/ads7846.dtbo
}
