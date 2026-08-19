SUMMARY = "LCD 3.5 Touchscreen Display Application"
DESCRIPTION = "Interactive touchscreen menu application for 3.5 inch LCD display"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI = " \
    file://lcd_menu.py \
    file://lcd_info.py \
    file://touch_draw.py \
    file://lcd-display.service \
    file://lcd-setup.sh \
    file://lcd-setup.service \
    file://lcd-screen \
"

# Get overlay files from kernel build
do_install[depends] += "linux-raspberrypi:do_deploy"

S = "${WORKDIR}"

RDEPENDS:${PN} = "python3-core bash"

inherit systemd

SYSTEMD_SERVICE:${PN} = "lcd-display.service lcd-setup.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    # Install Python applications
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/lcd_menu.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/lcd_info.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/touch_draw.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/lcd-screen ${D}${bindir}/
    
    # Install LCD setup script
    install -d ${D}${sbindir}
    install -m 0755 ${WORKDIR}/lcd-setup.sh ${D}${sbindir}/
    
    # Install systemd services
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/lcd-display.service ${D}${systemd_unitdir}/system/
    install -m 0644 ${WORKDIR}/lcd-setup.service ${D}${systemd_unitdir}/system/
    
    # Install overlay files to system directory for lcd-setup.sh
    install -d ${D}${datadir}/lcd-overlays
    
    # Copy overlays from deploy directory
    if [ -f ${DEPLOY_DIR_IMAGE}/bcm2835-bootfiles/overlays/tft35a.dtbo ]; then
        install -m 0644 ${DEPLOY_DIR_IMAGE}/bcm2835-bootfiles/overlays/tft35a.dtbo ${D}${datadir}/lcd-overlays/
    else
        bbwarn "tft35a.dtbo not found in deploy directory"
    fi
    
    if [ -f ${DEPLOY_DIR_IMAGE}/bcm2835-bootfiles/overlays/ads7846.dtbo ]; then
        install -m 0644 ${DEPLOY_DIR_IMAGE}/bcm2835-bootfiles/overlays/ads7846.dtbo ${D}${datadir}/lcd-overlays/
    else
        bbwarn "ads7846.dtbo not found in deploy directory"
    fi
}

FILES:${PN} += " \
    ${systemd_unitdir}/system/lcd-display.service \
    ${systemd_unitdir}/system/lcd-setup.service \
    ${sbindir}/lcd-setup.sh \
    ${datadir}/lcd-overlays \
"
