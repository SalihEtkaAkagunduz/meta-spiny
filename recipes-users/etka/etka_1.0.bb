SUMMARY = "Add etka user"
DESCRIPTION = "Recipe to add a regular user named etka with home directory"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit useradd

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "  -d /home/etka -m -s /bin/sh -p '\$1\$6kq4EhFO\$5ceJ6YmCgy470Eep.na8Y0' etka"

ALLOW_EMPTY:${PN} = "1"