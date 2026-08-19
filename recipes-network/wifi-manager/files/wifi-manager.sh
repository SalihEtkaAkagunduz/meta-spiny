#!/bin/sh
# SpinyOS WiFi Manager — state machine
#
# States:
#   CONFIGURED=false  → AP mode (first setup)
#   CONFIGURED=true   → try saved WiFi → if fail → AP mode (wifi_error fallback)
#
# Provisioning API (AP mode, 192.168.73.1:7373):
#   GET  /api/wifi/status      → {"status": "first_setup" | "wifi_error" | "ok", ...}
#   GET  /api/system/info      → {"hostname": ..., "device": "SpinyOS", ...}
#   POST /api/wifi/configure   → {"ssid": "...", "password": "..."}

PATH=/sbin:/usr/sbin:/bin:/usr/bin

STATE_FILE=/etc/spiny/wifi-state
CRED_FILE=/etc/spiny/wifi-credentials
LOG=/var/log/wifi-manager.log
READY_ACK_FILE=/run/spiny/ready-ack
READY_NOTIFIER_PID=/run/spiny/ready-notifier.pid

# Load device identity (written by device-identity.service which runs before us)
# Fallback: read directly if file exists, otherwise use generic placeholder
_ID_FILE=/run/spiny/device-id
if [ ! -f "$_ID_FILE" ]; then
    _ID_FILE=/etc/spiny/device-id
fi
if [ -f "$_ID_FILE" ]; then
    # shellcheck disable=SC1090
    . "$_ID_FILE"
fi
SPINY_DEVICE_ID="${SPINY_DEVICE_ID:-00000000}"

AP_SSID="spinyos-${SPINY_DEVICE_ID}"
AP_PSK="spiny1234"
AP_IP="192.168.73.1"
AP_CHANNEL="6"
PROVISION_PORT=7373
ETH_IFACE=eth0

MAX_RETRIES=2
ASSOC_TIMEOUT=15
PROVISIONING_MAX_RETRIES=2
PROVISIONING_ASSOC_TIMEOUT=10
CONNECTIVITY_CHECK_INTERVAL=5
CONNECTIVITY_FAIL_THRESHOLD=2
RECONNECT_SCAN_INTERVAL=10

# ---------------------------------------------------------------------------
log() {
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
    echo "$ts wifi-manager: $1" >> "$LOG" 2>/dev/null || true
    logger -t wifi-manager "$1" 2>/dev/null || true
}

ethernet_link_up() {
    if ! ip link show "$ETH_IFACE" >/dev/null 2>&1; then
        return 1
    fi

    if [ -r "/sys/class/net/$ETH_IFACE/carrier" ]; then
        [ "$(cat "/sys/class/net/$ETH_IFACE/carrier" 2>/dev/null)" = "1" ] && return 0
    fi

    _operstate="$(cat "/sys/class/net/$ETH_IFACE/operstate" 2>/dev/null)"
    [ "$_operstate" = "up" ] || [ "$_operstate" = "unknown" ]
}

internet_reachable() {
    # Ethernet varsa internet kontrolunu oradan gecerli kabul et.
    if ethernet_link_up; then
        return 0
    fi

    if ! ip -4 addr show dev wlan0 2>/dev/null | grep -q "inet "; then
        return 1
    fi

    if command -v ping >/dev/null 2>&1; then
        if ping -I wlan0 -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
            return 0
        fi
        if ping -I wlan0 -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
            return 0
        fi
    else
        # En azindan default rota varligini dogrula.
        if ip route get 1.1.1.1 >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

# Source state file; sets CONFIGURED, LAST_ERROR, STATUS, TARGET_SSID,
# CALLBACK_URL and READY_NOTIFIED variables
read_state() {
    CONFIGURED=false
    LAST_ERROR=""
    STATUS="first_setup"
    TARGET_SSID=""
    CALLBACK_URL=""
    READY_NOTIFIED=false
    if [ -f "$STATE_FILE" ]; then
        # shellcheck disable=SC1090
        . "$STATE_FILE"
    fi
}

write_state() {
    # $1 = configured, $2 = last_error, $3 = status, $4 = target_ssid,
    # $5 = callback_url, $6 = ready_notified
    mkdir -p "$(dirname "$STATE_FILE")"
    printf 'CONFIGURED=%s\n' "$1" > "$STATE_FILE"
    printf 'LAST_ERROR=%s\n' "'${2}'" >> "$STATE_FILE"
    printf 'STATUS=%s\n' "'${3}'" >> "$STATE_FILE"
    printf 'TARGET_SSID=%s\n' "'${4}'" >> "$STATE_FILE"
    printf 'CALLBACK_URL=%s\n' "'${5}'" >> "$STATE_FILE"
    printf 'READY_NOTIFIED=%s\n' "$6" >> "$STATE_FILE"
    chmod 600 "$STATE_FILE"
    log "state updated: configured=$1 status=$3 target_ssid=$4 last_error=$2 ready_notified=$6"
}

read_credentials() {
    WIFI_SSID=""
    WIFI_PASSWORD=""
    WIFI_IDENTITY=""
    WIFI_KEY_MGMT=""
    WIFI_EAP=""
    WIFI_PHASE2=""

    if [ ! -f "$CRED_FILE" ]; then
        return 1
    fi

    if python3 - <<'PY' "$CRED_FILE" 2>/tmp/wifi-cred-parse.err >/tmp/wifi-cred-parse.out
import json
import sys

path = sys.argv[1]
with open(path, encoding='utf-8') as handle:
    first = handle.read(1)
    handle.seek(0)
    if first == '{':
        data = json.load(handle)
        for key in ["WIFI_SSID", "WIFI_PASSWORD", "WIFI_IDENTITY", "WIFI_KEY_MGMT", "WIFI_EAP", "WIFI_PHASE2"]:
            value = str(data.get(key, ""))
            print(f"{key}={value}")
    else:
        raise SystemExit(1)
PY
    then
        while IFS='=' read -r key value; do
            case "$key" in
                WIFI_SSID) WIFI_SSID="$value" ;;
                WIFI_PASSWORD) WIFI_PASSWORD="$value" ;;
                WIFI_IDENTITY) WIFI_IDENTITY="$value" ;;
                WIFI_KEY_MGMT) WIFI_KEY_MGMT="$value" ;;
                WIFI_EAP) WIFI_EAP="$value" ;;
                WIFI_PHASE2) WIFI_PHASE2="$value" ;;
            esac
        done < /tmp/wifi-cred-parse.out
        log "credentials loaded from JSON — ssid='${WIFI_SSID}' password='${WIFI_PASSWORD}' identity='${WIFI_IDENTITY}' key_mgmt='${WIFI_KEY_MGMT}'"
        return 0
    fi

    # Backward compatibility with old shell format
    # shellcheck disable=SC1090
    . "$CRED_FILE"
    if [ -z "$WIFI_PASSWORD" ] && [ -n "$WIFI_PSK" ]; then
        WIFI_PASSWORD="$WIFI_PSK"
    fi
    log "credentials loaded from legacy shell format — ssid='${WIFI_SSID}' password='${WIFI_PASSWORD}' identity='${WIFI_IDENTITY}' key_mgmt='${WIFI_KEY_MGMT}'"
    return 0
}

stop_ready_notifier() {
    kill "$(cat "$READY_NOTIFIER_PID" 2>/dev/null)" 2>/dev/null || true
    rm -f "$READY_NOTIFIER_PID"
}

start_ready_notifier() {
    _target_ssid="$1"

    if [ -z "$CALLBACK_URL" ]; then
        log "no callback_url set, skipping ready notifier"
        return 0
    fi

    mkdir -p /run/spiny
    rm -f "$READY_ACK_FILE"
    stop_ready_notifier

    _hostname="${SPINY_HOSTNAME:-spinyos-${SPINY_DEVICE_ID}}"
    _api_base_url="http://${_hostname}.local:${PROVISION_PORT}"

    python3 /usr/bin/wifi-ready-notifier.py \
        "$CALLBACK_URL" \
        "$READY_ACK_FILE" \
        "$SPINY_DEVICE_ID" \
        "$_hostname" \
        "$_target_ssid" \
        "$_api_base_url" \
        10 &

    echo $! > "$READY_NOTIFIER_PID"
    log "ready notifier started for callback_url=$CALLBACK_URL"
}

start_api_server() {
    if [ -f /run/wifi-provision.pid ] && kill -0 "$(cat /run/wifi-provision.pid 2>/dev/null)" 2>/dev/null; then
        return 0
    fi

    python3 /usr/bin/wifi-provision-server.py "$PROVISION_PORT" >> /var/log/wifi-provision.log 2>&1 &
    echo $! > /run/wifi-provision.pid
    sleep 1
    if kill -0 "$(cat /run/wifi-provision.pid 2>/dev/null)" 2>/dev/null; then
        log "API server ready on port ${PROVISION_PORT}"
    else
        log "API server failed to stay up on port ${PROVISION_PORT}; see /var/log/wifi-provision.log"
        rm -f /run/wifi-provision.pid
        return 1
    fi
}

stop_api_server() {
    kill "$(cat /run/wifi-provision.pid 2>/dev/null)" 2>/dev/null || true
    rm -f /run/wifi-provision.pid
}

stop_ap_stack() {
    kill "$(cat /run/dnsmasq-spiny.pid 2>/dev/null)" 2>/dev/null || true
    kill "$(cat /run/hostapd-spiny.pid 2>/dev/null)" 2>/dev/null || true
    rm -f /run/dnsmasq-spiny.pid /run/hostapd-spiny.pid
    killall hostapd 2>/dev/null || true
    sleep 1
}

# ---------------------------------------------------------------------------
# AP mode helpers
# ---------------------------------------------------------------------------
start_ap_mode() {
    if ethernet_link_up; then
        log "ethernet link active on $ETH_IFACE — skipping WiFi AP and keeping API server available on Ethernet"
        stop_ready_notifier
        rm -f "$READY_ACK_FILE"
        killall wpa_supplicant 2>/dev/null || true
        stop_ap_stack
        start_api_server
        return 0
    fi

    log "starting AP mode  ssid=$AP_SSID"
    stop_ready_notifier
    rm -f "$READY_ACK_FILE"

    # Stop any existing client connections
    killall wpa_supplicant 2>/dev/null || true
    stop_ap_stack

    # Configure interface
    ip link set wlan0 up
    ip addr flush dev wlan0
    ip addr add "${AP_IP}/24" dev wlan0

    # hostapd config — country_code kullanmiyoruz; bazı platformlarda geçersiz
    # kod veya eksik regdb yüzünden AP hiç kalkmıyor.
    HOSTAPD_CONF=/tmp/spiny-hostapd.conf
    HOSTAPD_LOG=/tmp/hostapd-spiny.log
    start_hostapd() {
        _channel="$1"
        cat > "$HOSTAPD_CONF" <<HAEOF
interface=wlan0
driver=nl80211
ctrl_interface=/var/run/hostapd
ssid=${AP_SSID}
hw_mode=g
channel=${_channel}
beacon_int=100
dtim_period=2
wmm_enabled=1
ignore_broadcast_ssid=0
macaddr_acl=0
auth_algs=1
wpa=2
wpa_passphrase=${AP_PSK}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
HAEOF
        chmod 600 "$HOSTAPD_CONF"
        hostapd -B "$HOSTAPD_CONF" -P /run/hostapd-spiny.pid > "$HOSTAPD_LOG" 2>&1
    }

    if start_hostapd "$AP_CHANNEL"; then
        log "hostapd started (AP: $AP_SSID channel=$AP_CHANNEL)"
    elif [ "$AP_CHANNEL" != "1" ] && start_hostapd 1; then
        log "hostapd started with fallback channel=1 (AP: $AP_SSID)"
    elif [ "$AP_CHANNEL" != "6" ] && start_hostapd 6; then
        log "hostapd started with fallback channel=6 (AP: $AP_SSID)"
    else
        log "hostapd failed — output: $(cat "$HOSTAPD_LOG" 2>/dev/null)"
    fi

    # dnsmasq: DHCP for AP clients only
    DNSMASQ_CONF=/tmp/spiny-dnsmasq.conf
    cat > "$DNSMASQ_CONF" <<DMEOF
interface=wlan0
bind-interfaces
port=0
dhcp-authoritative
dhcp-range=192.168.73.10,192.168.73.50,255.255.255.0,24h
dhcp-option=3,${AP_IP}
dhcp-option=6,${AP_IP}
dhcp-leasefile=/run/dnsmasq-spiny.leases
pid-file=/run/dnsmasq-spiny.pid
log-facility=/var/log/dnsmasq-spiny.log
no-resolv
no-poll
DMEOF

    if ! dnsmasq -C "$DNSMASQ_CONF"; then
        log "dnsmasq failed to start — see /var/log/dnsmasq-spiny.log"
    fi

    # Provisioning/status HTTP server
    start_api_server
    log "AP mode ready — provisioning server on ${AP_IP}:${PROVISION_PORT}"
}

stop_ap_mode() {
    log "stopping AP mode"
    stop_api_server
    stop_ready_notifier
    stop_ap_stack
}

# ---------------------------------------------------------------------------
# WiFi client connection
# Returns: 0=success, 1=assoc_timeout, 2=dhcp_fail, 3=auth_fail
# ---------------------------------------------------------------------------
connect_wifi() {
    _ssid="$1"
    _password="$2"
    _identity="$3"
    _key_mgmt="$4"
    _eap="$5"
    _phase2="$6"

    log "connecting to ssid=$_ssid"

    # Kill leftover AP processes
    stop_ap_mode 2>/dev/null || true
    killall wpa_supplicant 2>/dev/null || true
    sleep 1

    ip link set wlan0 up
    ip addr flush dev wlan0

    WPA_CONF=/tmp/spiny-wpa.conf
    {
        echo "ctrl_interface=DIR=/var/run/wpa_supplicant"
        echo "update_config=0"
        echo "network={"
        echo "    ssid=\"$_ssid\""

        if [ "$_key_mgmt" = "WPA-EAP" ] && [ -n "$_identity" ]; then
            echo "    key_mgmt=WPA-EAP"
            echo "    eap=${_eap:-PEAP}"
            echo "    identity=\"$_identity\""
            echo "    password=\"$_password\""
            echo "    phase2=\"${_phase2:-auth=MSCHAPV2}\""
        else
            echo "    key_mgmt=WPA-PSK"
            echo "    psk=\"$_password\""
        fi

        echo "}"
    } > "$WPA_CONF"
    chmod 600 "$WPA_CONF"

    if ! wpa_supplicant -B -i wlan0 -c "$WPA_CONF"; then
        log "wpa_supplicant failed to start"
        return 1
    fi

    # Wait for association
    i=0
    while [ "$i" -lt "$ASSOC_TIMEOUT" ]; do
        state=""
        if command -v wpa_cli >/dev/null 2>&1; then
            state="$(wpa_cli -i wlan0 status 2>/dev/null | awk -F= '/^wpa_state/{print $2}')"
        fi
        if [ "$state" = "COMPLETED" ]; then
            log "associated with $_ssid"
            break
        fi
        # Detect explicit authentication failure early
        if [ "$state" = "DISCONNECTED" ] || [ "$state" = "INACTIVE" ]; then
            reason="$(wpa_cli -i wlan0 status 2>/dev/null | awk -F= '/^reason_code/{print $2}')"
            if [ -n "$reason" ] && [ "$reason" != "0" ]; then
                log "auth failed (reason=$reason)"
                killall wpa_supplicant 2>/dev/null || true
                return 3
            fi
        fi
        i=$((i + 1))
        sleep 1
    done

    if [ "$i" -ge "$ASSOC_TIMEOUT" ]; then
        log "association timeout for $_ssid"
        killall wpa_supplicant 2>/dev/null || true
        return 1
    fi

    # Request DHCP lease
    if udhcpc -i wlan0 -n -q -t 15 2>/tmp/udhcpc-spiny.err; then
        log "DHCP lease obtained"
        return 0
    else
        log "DHCP failed: $(cat /tmp/udhcpc-spiny.err 2>/dev/null)"
        killall wpa_supplicant 2>/dev/null || true
        return 2
    fi
}

connect_saved_wifi_profile() {
    read_state

    if [ "$CONFIGURED" != "true" ] || [ ! -f "$CRED_FILE" ]; then
        return 4
    fi

    if ! read_credentials; then
        log "failed to read credentials file"
        write_state "false" "invalid_credentials_file" "first_setup" "" "$CALLBACK_URL" "false"
        return 5
    fi

    if [ -z "$WIFI_KEY_MGMT" ]; then
        if [ -n "$WIFI_IDENTITY" ]; then
            WIFI_KEY_MGMT="WPA-EAP"
        else
            WIFI_KEY_MGMT="WPA-PSK"
        fi
    fi

    current_max_retries="$PROVISIONING_MAX_RETRIES"
    current_assoc_timeout="$PROVISIONING_ASSOC_TIMEOUT"

    if [ "$STATUS" = "credentials_received" ]; then
        log "provisioning retry profile active: retries=$current_max_retries timeout=${current_assoc_timeout}s ssid='$WIFI_SSID'"
    else
        log "reconnect retry profile active: retries=$current_max_retries timeout=${current_assoc_timeout}s ssid='$WIFI_SSID'"
    fi

    write_state "true" "" "connecting" "$WIFI_SSID" "$CALLBACK_URL" "false"

    attempt=0
    last_rc=1
    while [ "$attempt" -lt "$current_max_retries" ]; do
        attempt=$((attempt + 1))
        log "attempt $attempt/$current_max_retries for ssid=$WIFI_SSID key_mgmt=${WIFI_KEY_MGMT:-WPA-PSK}"
        ASSOC_TIMEOUT="$current_assoc_timeout"
        connect_wifi \
            "$WIFI_SSID" \
            "$WIFI_PASSWORD" \
            "$WIFI_IDENTITY" \
            "$WIFI_KEY_MGMT" \
            "$WIFI_EAP" \
            "$WIFI_PHASE2"
        last_rc=$?
        if [ "$last_rc" -eq 0 ]; then
            log "connected successfully"
            write_state "true" "" "connected" "$WIFI_SSID" "$CALLBACK_URL" "true"
            start_api_server
            start_ready_notifier "$WIFI_SSID"
            return 0
        fi
        log "attempt $attempt failed (rc=$last_rc) for ssid='$WIFI_SSID'"
        if [ "$attempt" -lt "$current_max_retries" ]; then
            log "waiting 3s before next retry"
            sleep 3
        fi
    done

    case "$last_rc" in
        1) err="ap_not_found"  ;;
        2) err="dhcp_fail"     ;;
        3) err="auth_fail"     ;;
        *) err="unknown"       ;;
    esac

    log "all retries exhausted — error=$err, keeping AP fallback active"
    write_state "true" "$err" "wifi_error" "$WIFI_SSID" "$CALLBACK_URL" "false"
    return "$last_rc"
}

monitor_connected_link() {
    _ssid="$1"
    _fail_count=0

    while true; do
        if internet_reachable; then
            _fail_count=0
        else
            _fail_count=$((_fail_count + 1))
            log "internet health check failed for ssid='$_ssid' (count=${_fail_count}/${CONNECTIVITY_FAIL_THRESHOLD})"
            if [ "$_fail_count" -ge "$CONNECTIVITY_FAIL_THRESHOLD" ]; then
                log "internet lost for ssid='$_ssid' — switching to AP mode"
                write_state "true" "internet_lost" "wifi_error" "$_ssid" "$CALLBACK_URL" "false"
                return 1
            fi
        fi

        sleep "$CONNECTIVITY_CHECK_INTERVAL"
    done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
mkdir -p /var/log /etc/spiny
log "wifi-manager starting"

# ---------------------------------------------------------------------------
# wlan0 arayüzünü hazırla
# ---------------------------------------------------------------------------
# 1. Pi 4'te WiFi varsayılan olarak rfkill soft-block altında olabilir
if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock wifi 2>/dev/null || true
    rfkill unblock wlan 2>/dev/null || true
fi

# 2. wlan0 arayüzü henüz yoksa firmware yüklenene kadar bekle (maks 30 sn)
i=0
while [ "$i" -lt 30 ]; do
    if ip link show wlan0 >/dev/null 2>&1; then
        log "wlan0 interface found"
        break
    fi
    i=$((i + 1))
    sleep 1
done

if ! ip link show wlan0 >/dev/null 2>&1; then
    log "ERROR: wlan0 interface not found after 30s — check firmware"
    exit 1
fi

read_state

# Check if TCP/Broker connection is active
TCP_ACTIVE=false
if [ -f "/etc/spiny/tcp_config.json" ]; then
    if python3 -c "import json; print(json.load(open('/etc/spiny/tcp_config.json')).get('active_status', False))" 2>/dev/null | grep -qi "true"; then
        TCP_ACTIVE=true
    fi
fi

if [ "$TCP_ACTIVE" = "true" ]; then
    log "TCP active mode is enabled. Checking connection profile..."
    if [ "$CONFIGURED" = "true" ] && [ -f "$CRED_FILE" ]; then
        if connect_saved_wifi_profile; then
            # Wait up to 60 seconds for TCP connection to succeed
            log "WiFi connected. Waiting for TCP handshake..."
            i=0
            tcp_ok=false
            while [ "$i" -lt 60 ]; do
                TCP_STATUS="disconnected"
                if [ -f "/etc/spiny/tcp-state.json" ]; then
                    TCP_STATUS=$(python3 -c "import json; print(json.load(open('/etc/spiny/tcp-state.json')).get('status', 'disconnected'))" 2>/dev/null)
                fi
                
                if [ "$TCP_STATUS" = "connected" ]; then
                    log "TCP handshake successful!"
                    tcp_ok=true
                    break
                elif [ "$TCP_STATUS" = "failed" ]; then
                    log "TCP handshake failed explicitly."
                    break
                fi
                i=$((i + 1))
                sleep 1
            done
            
            if [ "$tcp_ok" = "true" ]; then
                log "TCP connection active. Monitoring link..."
                # Monitor client link. If link is lost or TCP status becomes failed, fall back.
                while true; do
                    if ! internet_reachable; then
                        log "Internet link lost in TCP mode."
                        break
                    fi
                    
                    TCP_STATUS="disconnected"
                    if [ -f "/etc/spiny/tcp-state.json" ]; then
                        TCP_STATUS=$(python3 -c "import json; print(json.load(open('/etc/spiny/tcp-state.json')).get('status', 'disconnected'))" 2>/dev/null)
                    fi
                    
                    if [ "$TCP_STATUS" = "failed" ]; then
                        log "TCP connection failed during run. Falling back to AP mode."
                        break
                    fi
                    sleep 5
                done
            else
                log "TCP handshake failed or timed out. Falling back to AP mode."
            fi
        else
            log "Saved WiFi profile connection failed. Falling back to AP mode."
        fi
    else
        log "WiFi not configured in TCP active mode. Falling back to AP mode."
    fi
fi

if [ "$CONFIGURED" = "true" ] && [ -f "$CRED_FILE" ]; then
    if connect_saved_wifi_profile; then
        monitor_connected_link "$WIFI_SSID" || true
    else
        log "initial WiFi connect failed — AP fallback will start"
    fi
else
    log "not configured — starting AP mode for first setup"
    write_state "false" "" "first_setup" "" "$CALLBACK_URL" "false"
fi

start_ap_mode

# Block; keep AP state aligned with Ethernet presence and watchdog hostapd health.
ap_suppressed_for_eth=false
reconnect_tick=0
while true; do
    if ethernet_link_up; then
        if [ "$ap_suppressed_for_eth" != "true" ]; then
            log "ethernet link detected on $ETH_IFACE — disabling WiFi AP, API available on Ethernet"
            stop_ap_stack
            start_api_server
            ap_suppressed_for_eth=true
        fi
        reconnect_tick=0
    else
        if [ "$ap_suppressed_for_eth" = "true" ]; then
            log "ethernet link removed on $ETH_IFACE — re-enabling WiFi AP"
            start_ap_mode
            ap_suppressed_for_eth=false
        else
            # AP health watchdog: hostapd öldüyse yeniden başlat
            if ! kill -0 "$(cat /run/hostapd-spiny.pid 2>/dev/null)" 2>/dev/null; then
                log "hostapd not running — restarting AP mode"
                start_ap_mode
            fi

            reconnect_tick=$((reconnect_tick + 5))
            if [ "$reconnect_tick" -ge "$RECONNECT_SCAN_INTERVAL" ]; then
                reconnect_tick=0
                read_state
                if [ "$CONFIGURED" = "true" ] && [ -f "$CRED_FILE" ]; then
                    log "AP mode reconnect probe — trying saved network"
                    if connect_saved_wifi_profile; then
                        log "saved network restored — AP will stop while WiFi client mode is active"
                        monitor_connected_link "$WIFI_SSID" || start_ap_mode
                    fi
                fi
            fi
        fi
    fi
    sleep 5
done
