FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += "file://99-fbdev-lcd.conf"

do_install:append() {
    install -d ${D}${datadir}/X11/xorg.conf.d
    install -m 0644 ${WORKDIR}/99-fbdev-lcd.conf ${D}${datadir}/X11/xorg.conf.d/
}

FILES:${PN} += "${datadir}/X11/xorg.conf.d/99-fbdev-lcd.conf"
