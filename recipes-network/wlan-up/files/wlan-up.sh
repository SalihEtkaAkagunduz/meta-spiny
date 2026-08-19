#!/bin/sh
# Enhanced wlan-up script: brings up wlan0, starts wpa_supplicant, requests DHCP,
# and writes detailed timestamped logs to /var/log/wlan-up.log and the journal.
PATH=/sbin:/usr/sbin:/bin:/usr/bin
LOGFILE=/var/log/wlan-up.log

log() {
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    # Ensure log directory and file exist if possible (don't fail if readonly)
    logdir="$(dirname "$LOGFILE")"
    if [ ! -d "$logdir" ]; then
        mkdir -p "$logdir" 2>/dev/null || true
    fi
    touch "$LOGFILE" 2>/dev/null || true

    # append to persistent logfile (ignore errors)
    echo "$ts wlan-up: $1" >> "$LOGFILE" 2>/dev/null || true

    # also append to /root/log.txt only if /root exists (ignore errors)
    if [ -d /root ]; then
        echo "$ts wlan-up: $1" >> /root/log.txt 2>/dev/null || true
    fi

    # also append to /home/root/log.txt if /home/root exists (ignore errors)
    if [ -d /home/root ]; then
        echo "$ts wlan-up: $1" >> /home/root/log.txt 2>/dev/null || true
    fi

    # call logger only if present in PATH
    if command -v logger >/dev/null 2>&1; then
        logger -t wlan-up "$1" || true
    fi
}

do_up() {
    log "starting wlan-up script"
    if command -v ip >/dev/null 2>&1; then
        if ip link set wlan0 up >/tmp/wlan-up-ip.out 2>/tmp/wlan-up-ip.err; then
            log "brought wlan0 up with ip"
        else
            log "ip link set wlan0 up failed; stdout:$(cat /tmp/wlan-up-ip.out 2>/dev/null) stderr:$(cat /tmp/wlan-up-ip.err 2>/dev/null)"
        fi
    elif command -v ifconfig >/dev/null 2>&1; then
        if ifconfig wlan0 up >/tmp/wlan-up-ifconfig.out 2>/tmp/wlan-up-ifconfig.err; then
            log "brought wlan0 up with ifconfig"
        else
            log "ifconfig wlan0 up failed; stdout:$(cat /tmp/wlan-up-ifconfig.out 2>/dev/null) stderr:$(cat /tmp/wlan-up-ifconfig.err 2>/dev/null)"
        fi
    else
        log "no ip or ifconfig available to bring up wlan0"
    fi

    # Start wpa_supplicant if config exists and wpa_supplicant binary is present
    associated=0
    if [ -r /etc/wpa_supplicant.conf ] && command -v wpa_supplicant >/dev/null 2>&1; then
        if ! pgrep -f "wpa_supplicant.*wlan0" >/dev/null 2>&1; then
            log "starting wpa_supplicant for wlan0"
            if wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf >/tmp/wpa_supplicant.out 2>/tmp/wpa_supplicant.err; then
                log "wpa_supplicant started"
            else
                log "wpa_supplicant failed to start; stdout:$(cat /tmp/wpa_supplicant.out 2>/dev/null) stderr:$(cat /tmp/wpa_supplicant.err 2>/dev/null)"
            fi
        else
            log "wpa_supplicant already running for wlan0"
        fi

        # Wait for association before requesting DHCP. Check via wpa_cli (preferred) or iw as fallback.
        for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
            # check wpa_cli state
            if command -v wpa_cli >/dev/null 2>&1; then
                state=$(wpa_cli -i wlan0 status 2>/dev/null | awk -F= '/^wpa_state/ {print $2}')
                if [ "x$state" = "xCOMPLETED" ]; then
                    log "wpa_supplicant: association complete (wpa_cli)"
                    associated=1
                    break
                fi
            fi

            # fallback to iw link
            if command -v iw >/dev/null 2>&1; then
                if iw dev wlan0 link 2>/dev/null | grep -q "Connected to"; then
                    log "wpa_supplicant: association complete (iw)"
                    associated=1
                    break
                fi
            fi

            sleep 1
        done

        if [ "$associated" -ne 1 ]; then
            log "timed out waiting for association; will still attempt DHCP once"
        fi
    else
        log "no wpa_supplicant config or binary available"
    fi

    # Try to get IP via DHCP using udhcpc or dhclient, capture outputs
    if command -v udhcpc >/dev/null 2>&1; then
        log "requesting DHCP via udhcpc"
        if udhcpc -i wlan0 -q >/tmp/udhcpc.out 2>/tmp/udhcpc.err; then
            log "udhcpc succeeded"
        else
            log "udhcpc failed; stdout:$(cat /tmp/udhcpc.out 2>/dev/null) stderr:$(cat /tmp/udhcpc.err 2>/dev/null)"
        fi
    elif command -v dhclient >/dev/null 2>&1; then
        log "requesting DHCP via dhclient"
        if dhclient wlan0 >/tmp/dhclient.out 2>/tmp/dhclient.err; then
            log "dhclient succeeded"
        else
            log "dhclient failed; stdout:$(cat /tmp/dhclient.out 2>/dev/null) stderr:$(cat /tmp/dhclient.err 2>/dev/null)"
        fi
    else
        log "no DHCP client available"
    fi
}

run_once() {
    do_up
}

run_foreground() {
    log "starting wlan-up foreground manager"

    # Ensure wlan0 is up before starting wpa_supplicant in foreground
    if command -v ip >/dev/null 2>&1; then
        ip link set wlan0 up >/dev/null 2>&1 || true
    elif command -v ifconfig >/dev/null 2>&1; then
        ifconfig wlan0 up >/dev/null 2>&1 || true
    fi

    # Loop forever: ensure wpa_supplicant is running in foreground and dhcp configured
    while true; do
        # start wpa_supplicant in foreground if config exists
        if [ -r /etc/wpa_supplicant.conf ] && command -v wpa_supplicant >/dev/null 2>&1; then
            log "launching wpa_supplicant in foreground"
            # Run wpa_supplicant in foreground; when it exits, we will retry after a delay
            /sbin/wpa_supplicant -i wlan0 -c /etc/wpa_supplicant.conf -D nl80211
            rc=$?
            log "wpa_supplicant exited with code $rc"
        else
            log "wpa_supplicant not available or config missing"
            rc=1
        fi

        # If wpa_supplicant exited successfully, try DHCP once
        if [ "$rc" -eq 0 ]; then
            if command -v udhcpc >/dev/null 2>&1; then
                log "requesting DHCP via udhcpc"
                udhcpc -i wlan0 -q >/tmp/udhcpc.out 2>/tmp/udhcpc.err || true
            elif command -v dhclient >/dev/null 2>&1; then
                log "requesting DHCP via dhclient"
                dhclient wlan0 >/tmp/dhclient.out 2>/tmp/dhclient.err || true
            else
                log "no DHCP client available"
            fi
        fi

        # Wait before retrying (give time for link to settle)
        log "wlan-up manager sleeping 5s before retry"
        sleep 5
    done
}

# Allow both being called directly (systemd ExecStart) or as init script with 'start'
PIDFILE=/run/wlan-up.pid

start_bg() {
    log "start requested (background mode)"

    # bring interface up
    if command -v ip >/dev/null 2>&1; then
        ip link set wlan0 up >/dev/null 2>&1 || true
    elif command -v ifconfig >/dev/null 2>&1; then
        ifconfig wlan0 up >/dev/null 2>&1 || true
    fi

    # if already running, do nothing
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
            log "wpa_supplicant already running with pid $pid"
            return 0
        else
            log "stale pidfile found, removing"
            rm -f "$PIDFILE" 2>/dev/null || true
        fi
    fi

    # start wpa_supplicant in background if config exists
    if [ -r /etc/wpa_supplicant.conf ] && command -v wpa_supplicant >/dev/null 2>&1; then
        log "starting wpa_supplicant in background"
        # use -B to background; capture pid from pgrep or from $! if backgrounded
        wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf -D nl80211 >/tmp/wpa_supplicant.out 2>/tmp/wpa_supplicant.err || true
        # try to find pid
        pid=$(pgrep -f "wpa_supplicant.*wlan0" | head -n1 || true)
        if [ -n "$pid" ]; then
            echo "$pid" > "$PIDFILE" 2>/dev/null || true
            log "wpa_supplicant started with pid $pid"
        else
            log "failed to determine wpa_supplicant pid"
            return 1
        fi
    else
        log "wpa_supplicant not available or config missing"
        return 1
    fi

    # do a single DHCP attempt
    if command -v udhcpc >/dev/null 2>&1; then
        log "requesting DHCP via udhcpc"
        udhcpc -i wlan0 -q >/tmp/udhcpc.out 2>/tmp/udhcpc.err || true
    elif command -v dhclient >/dev/null 2>&1; then
        log "requesting DHCP via dhclient"
        dhclient wlan0 >/tmp/dhclient.out 2>/tmp/dhclient.err || true
    else
        log "no DHCP client available"
    fi

    return 0
}

stop_bg() {
    log "stop requested"
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE" 2>/dev/null || true)
        if [ -n "$pid" ]; then
            log "killing pid $pid"
            kill "$pid" >/dev/null 2>&1 || true
            # give some time
            sleep 1
            kill -0 "$pid" >/dev/null 2>&1 || true
        fi
        rm -f "$PIDFILE" 2>/dev/null || true
    else
        log "no pidfile, attempting pkill"
        pkill -f "wpa_supplicant.*wlan0" >/dev/null 2>&1 || true
    fi
}

if [ "$1" = "start" ]; then
    start_bg
    exit $?
fi

if [ "$1" = "stop" ]; then
    stop_bg
    exit $?
fi

if [ "$1" = "foreground" ]; then
    run_foreground
    exit 0
fi

# default: run once
if [ "$#" -eq 0 ]; then
    run_once
    exit 0
fi

exit 0
