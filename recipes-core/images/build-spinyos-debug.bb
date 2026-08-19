SUMMARY = "SpinyOS Debug Image"
DESCRIPTION = "Debug image with eduroam auto-connect. Use: bitbake build-spinyos-debug"
LICENSE = "MIT"

# Inherits all settings from the production image
require recipes-core/images/build-spinyos.bb

# Override hostname for debug builds
set_hostname() {
    echo "SpinyOS-Debug" > ${IMAGE_ROOTFS}/etc/hostname
}

# In debug mode, ship the eduroam wpa_supplicant config (from wlan-up recipe)
# and enable the wlan-up service instead of wifi-manager.
# wifi-manager handles AP fallback; wlan-up handles direct eduroam.
IMAGE_INSTALL:remove = "wifi-manager"
IMAGE_INSTALL:append = " wlan-up"

# Mark build as debug so wifi-manager state is pre-configured for eduroam
# (wlan-up already installs /etc/wpa_supplicant.conf with eduroam credentials)
