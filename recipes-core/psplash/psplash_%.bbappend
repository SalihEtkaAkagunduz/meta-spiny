# Fix the broken psplash-raspberrypi-img.h from meta-raspberrypi
# The original file has invalid C macro names with hyphens (logo-img.h_IMG_*)
# We replace it with a corrected version based on the Poky image

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Keep using the same SPLASH_IMAGES setting, but our corrected file will be used
# SPLASH_IMAGES:rpi = "file://psplash-raspberrypi-img.h;outsuffix=raspberrypi"

