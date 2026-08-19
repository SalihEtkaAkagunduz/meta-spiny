SUMMARY = "Seazer Layer Hello application"
DESCRIPTION = "A simple, professional-style hello world application built with Makefile"
SECTION = "examples"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit useradd

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --no-create-home etka"

# Kaynak dosyalarımız files klasöründe
SRC_URI = "file://hello.c \
           file://Makefile"

# Kaynak dizini
S = "${WORKDIR}"

# Standart autotools yerine basit make kullanıyoruz
do_compile() {
    oe_runmake
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 hello ${D}${bindir}/helloworld
}
