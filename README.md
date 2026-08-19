# meta-spiny - SpinyOS Custom Yocto Layer

Custom Yocto/OpenEmbedded layer for SpinyOS distribution.

## SpinyOS Distribution

SpinyOS is a custom embedded Linux distribution built with Yocto Project, optimized for Raspberry Pi 4.

### Features

- **Custom Distribution**: SpinyOS 1.0
- **Target Platform**: Raspberry Pi 4 (64-bit)
- **Init System**: systemd
- **Hostname**: SpinyOS-RaspberryPi4
- **Multi-language Help System**: English, Turkish, German, French, Arabic, Hindi
- **Custom Services**:
  - Telemetry service (device metrics)
  - Auto root filesystem resize
  - WiFi management
  
### System Identification

When you run `uname -a` on SpinyOS, you'll see:
```
Linux SpinyOS-RaspberryPi4 <kernel-version> #1 SMP <date> aarch64 GNU/Linux
```

OS Information (`cat /etc/os-release`):
```
NAME="SpinyOS"
VERSION="1.0 (Raspberry Pi 4 Edition)"
ID=spinyos
PRETTY_NAME="SpinyOS 1.0 (Raspberry Pi 4 Edition)"
VARIANT="Raspberry Pi 4 Edition"
VARIANT_ID=raspberrypi4
```

## Building SpinyOS

### Setup

1. Clone poky and required layers:
```bash
git clone git://git.yoctoproject.org/poky
cd poky
git clone git://git.openembedded.org/meta-openembedded
# Add meta-spiny layer
```

2. Initialize build environment:
```bash
source oe-init-build-env
```

3. Configure `conf/local.conf`:
```bash
MACHINE = "raspberrypi4-64"
DISTRO = "spinyos"
```

4. Add layers to `conf/bblayers.conf`:
```
BBLAYERS ?= " \\
  /path/to/poky/meta \\
  /path/to/poky/meta-poky \\
  /path/to/poky/meta-yocto-bsp \\
  /path/to/poky/meta-openembedded/meta-oe \\
  /path/to/poky/meta-openembedded/meta-python \\
  /path/to/poky/meta-openembedded/meta-networking \\
  /path/to/poky/meta-raspberrypi \\
  /path/to/poky/meta-spiny \\
"
```

### Build

```bash
bitbake build-spinyos
```

The output image will be in: `tmp/deploy/images/raspberrypi4-64/`

## Layer Contents

### Recipes

- **recipes-core/base-files**: Custom hostname, multi-language help system
- **recipes-core/os-release**: Custom OS identification
- **recipes-support/device-ingest**: Telemetry service
- **recipes-support/resize-rootfs**: Auto root filesystem resize on first boot
- **recipes-network/wlan-up**: WiFi management
- **recipes-apps/helloworld**: Example application
- **recipes-users/etka**: Custom user setup
- **recipes-drivers/lcd-touchscreen**: 3.5" LCD touchscreen driver and applications
- **recipes-drivers/nokia5110**: Nokia 5110 (84x48) LCD driver and applications

### Distribution Configuration

- **conf/distro/spinyos.conf**: SpinyOS distribution settings

### Commands Available in SpinyOS

- `help [language]` - Multi-language help (en, tr, de, fr, ar, hi)
- `telemetry` - Control telemetry service
- `systemctl` - Manage system services

### Orchestrator Node Control (`spinyctl`)

`spinyctl` can call the local orchestrator WebSocket API for managed ROS node operations.

Basic examples:

```bash
# List managed nodes
spinyctl orchestrator node list --json --token <TOKEN>

# Get one node status
spinyctl orchestrator node status demo_talker --json --token <TOKEN>

# Start/stop/restart a node
spinyctl orchestrator node start demo_talker --json --token <TOKEN>
spinyctl orchestrator node stop demo_talker --json --token <TOKEN> --grace-sec 3
spinyctl orchestrator node restart demo_talker --json --token <TOKEN>

# Get ROS2 graph snapshot (nodes/topics/services/actions)
spinyctl orchestrator graph snapshot --json --token <TOKEN>

# Inspect full I/O endpoints for one ROS2 node name
spinyctl orchestrator io /spiny/demo/spiny_demo_talker --json --token <TOKEN>

# Create bounded on-demand capture artifact (graph + optional node I/O)
spinyctl orchestrator capture window --duration-sec 5 --sample-interval-sec 1 --json --token <TOKEN>
spinyctl orchestrator capture window --duration-sec 10 --node-name /spiny/demo/spiny_demo_talker --json --token <TOKEN>

# Selective stream watch for one managed node (running/pid/state fields)
spinyctl orchestrator stream watch demo_talker --seconds 10 --rate-hz 1 --field running --field pid --field ros2State --json --token <TOKEN>

# Peer listesi ve uzak cihazdaki node kontrolu
spinyctl orchestrator peer list --json --token <TOKEN>
spinyctl orchestrator peer status peer-example demo_talker --json --token <TOKEN>
spinyctl orchestrator peer start peer-example demo_talker --json --token <TOKEN>
spinyctl orchestrator peer stop peer-example demo_talker --grace-sec 3 --json --token <TOKEN>
spinyctl orchestrator peer restart peer-example demo_talker --json --token <TOKEN>
```

Useful options:

- `--url` override default `ws://127.0.0.1:8765`
- `--timeout` request timeout in seconds
- `--token` explicit auth token (if omitted, `spinyctl` tries `/etc/spiny/orchestrator-auth.json`)
- `--auth-file` override token source file for auto token discovery

Node manifest inspection (file-based, no WebSocket call):

```bash
spinyctl orchestrator nodes --json
spinyctl orchestrator nodes --details --json
spinyctl orchestrator nodes --manifest /path/to/orchestrator-manifest.json --json
```

ROS2-native manifest node format (preferred):

```json
{
  "nodes": {
    "demo_talker": {
      "mode": "ros2",
      "package": "demo_nodes_cpp",
      "executable": "talker",
      "node_name": "spiny_demo_talker",
      "namespace": "/spiny/demo",
      "parameters": {
        "use_sim_time": false
      },
      "remaps": [
        "chatter:=/spiny/chatter"
      ],
      "lifecycle_mode": "process",
      "cwd": "/",
      "env": {
        "RMW_IMPLEMENTATION": "rmw_fastrtps_cpp"
      }
    }
  }
}
```

Legacy `start` command lists are still supported for backward compatibility.

`lifecycle_mode` values:

- `process`: only process lifecycle is managed (start/stop by PID)
- `managed`: ROS2 lifecycle transitions are applied (`configure` -> `activate`, and on stop `deactivate` -> `shutdown`)

Note: for `managed` mode, `node_name` must be set in manifest so the orchestrator can resolve the runtime ROS2 node name.

Peer allowlist dosyasi: `/etc/spiny/orchestrator-peers.json`

```json
{
  "peers": {
    "peer-example": {
      "url": "ws://192.168.1.50:8765",
      "token": "REPLACE_WITH_PEER_TOKEN",
      "allowRemoteControl": false,
      "allowedActions": [
        "node.status",
        "node.start",
        "node.stop",
        "node.restart"
      ]
    }
  }
}
```

ROS2 runtime dogrulama (hedef cihaz):

```bash
# Yeni shell acildiginda profile.d script ROS setup'i otomatik yukler
echo "$RMW_IMPLEMENTATION $ROS_DOMAIN_ID"

# ROS2 CLI ve graph komutlari
ros2 --help
ros2 node list

# Demo node kontrolu
spinyctl orchestrator node start demo_talker --json --token <TOKEN>
spinyctl orchestrator graph snapshot --json --token <TOKEN>
```

## Maintainer

SpinyOS Team <support@spinyos.local>

## License

MIT
