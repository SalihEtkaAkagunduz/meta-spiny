#!/usr/bin/env python3
"""SpinyOS Orchestrator

Implements a WebSocket v1 command channel focused on package management.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import pathlib
import re
import shutil
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import shlex

import websockets
import time

DEVICE_ID_FILE = "/run/spiny/device-id"
DEFAULT_POLICY_FILE = "/etc/spiny/orchestrator-policy.json"
DEFAULT_AUTH_FILE = "/etc/spiny/orchestrator-auth.json"
DEFAULT_MANIFEST_FILE = "/etc/spiny/orchestrator-manifest.json"
DEFAULT_PEERS_FILE = "/etc/spiny/orchestrator-peers.json"
DEFAULT_UPLOAD_DIR = "/tmp/spiny-orchestrator/uploads"
DEFAULT_CAPTURE_DIR = "/tmp/spiny-orchestrator/captures"

ROLE_PERMISSIONS = {
    "viewer": {
        "user.info",
        "pkg.status",
        "pkg.list",
        "pkg.missing",
        "node.list",
        "node.status",
        "graph.snapshot",
        "node.io.inspect",
        "capture.window",
        "stream.subscribe",
        "stream.unsubscribe",
        "peer.list",
        "peer.node.status",
    },
    "operator": {
        "user.info",
        "pkg.status",
        "pkg.list",
        "pkg.missing",
        "pkg.install",
        "pkg.upload.begin",
        "pkg.upload.chunk",
        "pkg.upload.commit",
        "pkg.upload.abort",
        "node.list",
        "node.status",
        "node.start",
        "node.stop",
        "node.restart",
        "graph.snapshot",
        "node.io.inspect",
        "capture.window",
        "stream.subscribe",
        "stream.unsubscribe",
        "orchestrator.reload",
        "peer.list",
        "peer.node.status",
        "peer.node.start",
        "peer.node.stop",
        "peer.node.restart",
    },
    "admin": {
        "user.info",
        "pkg.status",
        "pkg.list",
        "pkg.missing",
        "pkg.install",
        "pkg.upload.begin",
        "pkg.upload.chunk",
        "pkg.upload.commit",
        "pkg.upload.abort",
        "node.list",
        "node.status",
        "node.start",
        "node.stop",
        "node.restart",
        "graph.snapshot",
        "node.io.inspect",
        "capture.window",
        "stream.subscribe",
        "stream.unsubscribe",
        "orchestrator.reload",
        "peer.list",
        "peer.node.status",
        "peer.node.start",
        "peer.node.stop",
        "peer.node.restart",
    },
}

VALID_ACTIONS = {
    "user.info",
    "pkg.status",
    "pkg.list",
    "pkg.missing",
    "pkg.install",
    "pkg.upload.begin",
    "pkg.upload.chunk",
    "pkg.upload.commit",
    "pkg.upload.abort",
    "node.list",
    "node.status",
    "node.start",
    "node.stop",
    "node.restart",
    "graph.snapshot",
    "node.io.inspect",
    "capture.window",
    "stream.subscribe",
    "stream.unsubscribe",
    "orchestrator.reload",
    "peer.list",
    "peer.node.status",
    "peer.node.start",
    "peer.node.stop",
    "peer.node.restart",
}


@dataclass
class Operation:
    operation_id: str
    action: str
    manager: str
    state: str
    created_at: str
    updated_at: str
    packages: List[str]
    result: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class UploadSession:
    upload_id: str
    manager: str
    artifact_type: str
    file_name: str
    size_bytes: int
    sha256: str
    target: str
    expected_seq: int
    bytes_received: int
    path: str
    created_ts: float = 0.0


@dataclass
class NodeRuntime:
    node_id: str
    process: asyncio.subprocess.Process
    started_at: str
    start_cmd: List[str]
    ros2_node_name: Optional[str] = None
    lifecycle_mode: str = "process"
    lifecycle_state: str = "inactive"


@dataclass
class StreamSubscription:
    subscription_id: str
    node_id: str
    fields: List[str]
    interval_sec: float
    websocket: websockets.WebSocketServerProtocol
    role: str
    task: asyncio.Task


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json_file(path: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parsed = json.load(handle)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass
    return fallback


def load_device_id() -> str:
    default = "spiny-unknown"
    try:
        with open(DEVICE_ID_FILE, "r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if line.startswith("SPINY_DEVICE_ID="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return default


def parse_token(path: str, headers: Dict[str, str]) -> Optional[str]:
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        return auth.replace("Bearer ", "", 1).strip()

    parsed = urllib.parse.urlparse(path)
    q = urllib.parse.parse_qs(parsed.query)
    token = q.get("token", [None])[0]
    if token:
        return token
    return None


class SpinyOrchestrator:
    def __init__(self) -> None:
        self.host = os.getenv("SPINY_ORCH_HOST", "0.0.0.0")
        self.port = int(os.getenv("SPINY_ORCH_PORT", "8765"))
        self.policy_file = os.getenv("SPINY_ORCH_POLICY_FILE", DEFAULT_POLICY_FILE)
        self.auth_file = os.getenv("SPINY_ORCH_AUTH_FILE", DEFAULT_AUTH_FILE)
        self.manifest_file = os.getenv("SPINY_ORCH_MANIFEST_FILE", DEFAULT_MANIFEST_FILE)
        self.peers_file = os.getenv("SPINY_ORCH_PEERS_FILE", DEFAULT_PEERS_FILE)
        self.upload_dir = os.getenv("SPINY_ORCH_UPLOAD_DIR", DEFAULT_UPLOAD_DIR)
        self.capture_dir = os.getenv("SPINY_ORCH_CAPTURE_DIR", DEFAULT_CAPTURE_DIR)
        self.ros_distro = os.getenv("SPINY_ROS_DISTRO", "humble")
        self.ros2_bin_hint = os.getenv(
            "SPINY_ORCH_ROS2_BIN",
            f"/opt/ros/{self.ros_distro}/bin/ros2",
        )
        self.default_rmw = os.getenv("SPINY_ORCH_DEFAULT_RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")
        self.default_ros_domain_id = os.getenv("SPINY_ORCH_DEFAULT_ROS_DOMAIN_ID", "0")
        self.default_ros_localhost_only = os.getenv("SPINY_ORCH_DEFAULT_ROS_LOCALHOST_ONLY", "0")
        self.ros2_bin = self._resolve_ros2_binary()

        # Environment Hardening (Ensure ROS 2 logging works out of the box)
        os.environ.setdefault("HOME", "/root")
        os.environ.setdefault("ROS_LOG_DIR", "/tmp/ros_logs")
        pathlib.Path("/tmp/ros_logs").mkdir(parents=True, exist_ok=True)

        self.device_id = load_device_id()
        self.policy = self._load_policy()
        self.tokens = self._load_tokens()
        self.managed_nodes = self._load_manifest_nodes()
        self.peers = self._load_peers()

        self.operations: Dict[str, Operation] = {}
        self.uploads: Dict[str, UploadSession] = {}
        self.node_runtimes: Dict[str, NodeRuntime] = {}
        # restart bookkeeping to avoid tight crash loops
        self._node_restart_info: Dict[str, Tuple[int, float]] = {}
        # per-process CPU sampling state: pid -> (last_cpu_seconds, last_ts)
        self._proc_cpu_state: Dict[int, Tuple[float, float]] = {}
        # rclpy probe node (optional, created lazily)
        self._rclpy_node = None
        self._rclpy_available = False
        self.stream_subscriptions: Dict[str, StreamSubscription] = {}
        self.connection_subscriptions: Dict[int, Set[str]] = {}
        self.running_operations = 0

        pathlib.Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.capture_dir).mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        self.logger = logging.getLogger("spiny-orchestrator")
        # detect whether rclpy is importable; actual init/node creation is lazy
        try:
            import importlib

            importlib.import_module("rclpy")
            self._rclpy_available = True
        except Exception:
            self._rclpy_available = False
            self._rclpy_node = None

    def _resolve_ros2_binary(self) -> str:
        candidate = str(self.ros2_bin_hint).strip()
        if candidate and os.path.exists(candidate):
            return candidate

        for fallback in ["/usr/bin/ros2", "/usr/local/bin/ros2"]:
            if os.path.exists(fallback):
                return fallback

        from_path = shutil.which("ros2")
        if from_path:
            return from_path

        return candidate or "/usr/bin/ros2"

    def _load_policy(self) -> Dict[str, Any]:
        defaults = {
            "maxUploadBytes": 104857600,
            "maxChunkBytes": 262144,
            "maxParallelOps": 2,
            "defaultSourcePolicy": "repo-only",
            "allowUrl": False,
            "allowedDomains": [],
            "blockedPackages": [],
            "pipBinaryOnly": True,
            "enableRollback": True,
            "rosWorkspaceRoot": "/home/root/spiny_ws",
            "externalLibDir": "/opt/spiny/external/lib",
            "ldSoConfFile": "/etc/ld.so.conf.d/spiny-external.conf",
        }
        return load_json_file(self.policy_file, defaults)

    def _load_tokens(self) -> Dict[str, str]:
        parsed = load_json_file(self.auth_file, {"tokens": {}})
        tokens = parsed.get("tokens", {})
        if isinstance(tokens, dict):
            return {str(k): str(v) for k, v in tokens.items()}
        return {}

    def _load_peers(self) -> Dict[str, Dict[str, Any]]:
        parsed = load_json_file(self.peers_file, {"peers": {}})
        peers = parsed.get("peers", {})
        if not isinstance(peers, dict):
            return {}

        clean: Dict[str, Dict[str, Any]] = {}
        for peer_id, cfg in peers.items():
            if not isinstance(peer_id, str) or not isinstance(cfg, dict):
                continue

            url = cfg.get("url")
            token = cfg.get("token", "")
            allow_remote = bool(cfg.get("allowRemoteControl", False))
            allowed_actions = cfg.get("allowedActions", [])

            if not isinstance(url, str) or not url.strip():
                continue
            if not isinstance(token, str):
                token = ""
            if not isinstance(allowed_actions, list):
                allowed_actions = []

            clean[peer_id] = {
                "url": url.strip(),
                "token": token.strip(),
                "allowRemoteControl": allow_remote,
                "allowedActions": [
                    str(item).strip()
                    for item in allowed_actions
                    if isinstance(item, str) and str(item).strip()
                ],
            }
        return clean

    def role_for_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        role = self.tokens.get(token)
        if role in ROLE_PERMISSIONS:
            return role
        return None

    def _load_manifest_nodes(self) -> Dict[str, Dict[str, Any]]:
        parsed = load_json_file(self.manifest_file, {"nodes": {}})
        nodes = parsed.get("nodes", {})
        if not isinstance(nodes, dict):
            return {}

        valid: Dict[str, Dict[str, Any]] = {}
        for node_id, config in nodes.items():
            if not isinstance(node_id, str) or not isinstance(config, dict):
                continue

            start_cmd = config.get("start")
            if not isinstance(start_cmd, list) or not start_cmd:
                start_cmd = None
            if start_cmd and not all(isinstance(item, str) and item.strip() for item in start_cmd):
                start_cmd = None

            ros2_cfg = self._parse_ros2_config(config)
            node_mode = str(config.get("mode", "")).strip().lower()
            if node_mode not in {"process", "ros2"}:
                node_mode = "ros2" if ros2_cfg else "process"

            if node_mode == "ros2" and ros2_cfg:
                start_cmd = self._build_ros2_start_command(ros2_cfg)
            elif start_cmd is None and ros2_cfg:
                start_cmd = self._build_ros2_start_command(ros2_cfg)

            if start_cmd is None:
                continue

            cwd = config.get("cwd")
            env = config.get("env", {})
            lifecycle_mode = str(config.get("lifecycle_mode", "process")).strip().lower()
            if lifecycle_mode not in {"process", "managed"}:
                lifecycle_mode = "process"

            if cwd is not None and not isinstance(cwd, str):
                cwd = None
            if not isinstance(env, dict):
                env = {}

            sanitized_env = {
                str(key): str(value)
                for key, value in env.items()
                if isinstance(key, str)
            }

            valid[node_id] = {
                "start": start_cmd,
                "cwd": cwd,
                "env": sanitized_env,
                "mode": node_mode,
                "lifecycle_mode": lifecycle_mode,
                "ros2": ros2_cfg,
            }

        return valid

    def _parse_ros2_config(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        package = config.get("package")
        executable = config.get("executable")
        if not isinstance(package, str) or not package.strip():
            return None
        if not isinstance(executable, str) or not executable.strip():
            return None

        node_name = config.get("node_name")
        namespace = config.get("namespace")
        arguments = config.get("arguments", [])
        parameters = config.get("parameters", {})
        remaps = config.get("remaps", [])

        if node_name is not None and (not isinstance(node_name, str) or not node_name.strip()):
            node_name = None
        if namespace is not None and (not isinstance(namespace, str) or not namespace.strip()):
            namespace = None
        if not isinstance(arguments, list):
            arguments = []
        if not isinstance(parameters, dict):
            parameters = {}
        if not isinstance(remaps, list):
            remaps = []

        clean_arguments = [str(item) for item in arguments if isinstance(item, str) and item.strip()]
        clean_parameters = {
            str(key): value
            for key, value in parameters.items()
            if isinstance(key, str) and key.strip()
        }

        clean_remaps = []
        for entry in remaps:
            if isinstance(entry, str) and entry.strip():
                clean_remaps.append(entry.strip())
                continue
            if not isinstance(entry, dict):
                continue
            source = entry.get("from")
            target = entry.get("to")
            if isinstance(source, str) and source.strip() and isinstance(target, str) and target.strip():
                clean_remaps.append(f"{source.strip()}:={target.strip()}")

        return {
            "package": package.strip(),
            "executable": executable.strip(),
            "node_name": node_name.strip() if isinstance(node_name, str) else None,
            "namespace": namespace.strip() if isinstance(namespace, str) else None,
            "arguments": clean_arguments,
            "parameters": clean_parameters,
            "remaps": clean_remaps,
        }

    def _ros_param_literal(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        return json.dumps(value, separators=(",", ":"), ensure_ascii=True)

    def _build_ros2_start_command(self, ros2_cfg: Dict[str, Any]) -> List[str]:
        cmd = [
            self.ros2_bin,
            "run",
            ros2_cfg["package"],
            ros2_cfg["executable"],
        ]

        arguments = ros2_cfg.get("arguments", [])
        if arguments:
            cmd.extend([str(item) for item in arguments])

        ros_args: List[str] = []
        node_name = ros2_cfg.get("node_name")
        namespace = ros2_cfg.get("namespace")

        if isinstance(node_name, str) and node_name:
            ros_args.extend(["-r", f"__node:={node_name}"])
        if isinstance(namespace, str) and namespace:
            ros_args.extend(["-r", f"__ns:={namespace}"])

        for rule in ros2_cfg.get("remaps", []):
            if isinstance(rule, str) and rule:
                ros_args.extend(["-r", rule])

        parameters = ros2_cfg.get("parameters", {})
        if isinstance(parameters, dict):
            for key in sorted(parameters.keys()):
                ros_args.extend(["-p", f"{key}:={self._ros_param_literal(parameters[key])}"])

        if ros_args:
            cmd.append("--ros-args")
            cmd.extend(ros_args)

        return cmd

    async def send_message(
        self,
        websocket: websockets.WebSocketServerProtocol,
        msg_type: str,
        action: str,
        request_id: Optional[str],
        role: Optional[str],
        payload: Dict[str, Any],
    ) -> None:
        msg = {
            "v": 1,
            "type": msg_type,
            "action": action,
            "requestId": request_id,
            "ts": utc_now(),
            "deviceId": self.device_id,
            "role": role,
            "payload": payload,
        }
        await websocket.send(json.dumps(msg, separators=(",", ":")))

    async def send_error(
        self,
        websocket: websockets.WebSocketServerProtocol,
        action: str,
        request_id: Optional[str],
        role: Optional[str],
        error_code: str,
        message: str,
        retryable: bool,
        details: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
    ) -> None:
        payload = {
            "operationId": operation_id,
            "errorCode": error_code,
            "retryable": retryable,
            "message": message,
            "details": details or {},
        }
        await self.send_message(websocket, "error", action, request_id, role, payload)

    def _validate_envelope(self, body: Dict[str, Any]) -> Optional[str]:
        if body.get("v") != 1:
            return "invalid version"
        if body.get("type") != "command":
            return "type must be command"
        if not isinstance(body.get("action"), str):
            return "action is required"
        if body.get("action") not in VALID_ACTIONS:
            return "unsupported action"
        if not isinstance(body.get("requestId"), str) or not body.get("requestId"):
            return "requestId is required"
        if not isinstance(body.get("payload"), dict):
            return "payload must be object"
        return None

    def _check_permission(self, role: str, action: str) -> bool:
        return action in ROLE_PERMISSIONS.get(role, set())

    async def _run_command(self, args: List[str], timeout: int = 300) -> Tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return 127, "", "binary not found"

        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                await proc.wait()
            except Exception:
                pass
            return 124, "", "timeout"

        return proc.returncode, out.decode("utf-8", errors="replace"), err.decode(
            "utf-8", errors="replace"
        )

    async def _append_to_file(self, path: str, data: bytes) -> None:
        def _write():
            with open(path, "ab") as fh:
                fh.write(data)

        await asyncio.to_thread(_write)

    async def _compute_file_sha256(self, path: str) -> str:
        def _digest():
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                while True:
                    block = fh.read(1024 * 1024)
                    if not block:
                        break
                    h.update(block)
            return h.hexdigest()

        return await asyncio.to_thread(_digest)

    async def _sample_process_metrics(self, pid: int, interval: float) -> Tuple[float, int]:
        # returns (cpu_percent, rss_kb)
        try:
            stat_path = f"/proc/{pid}/stat"
            status_path = f"/proc/{pid}/status"
            with open(stat_path, "r") as fh:
                parts = fh.read().split()
            # utime is at index 13, stime at 14 (0-based)
            utime = float(parts[13])
            stime = float(parts[14])
            total_ticks = utime + stime
            clk_tck = float(os.sysconf(os.sysconf_names["SC_CLK_TCK"]))
            total_seconds = total_ticks / clk_tck

            rss_kb = 0
            with open(status_path, "r") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        toks = line.split()
                        if len(toks) >= 2:
                            try:
                                rss_kb = int(toks[1])
                            except Exception:
                                rss_kb = 0
                        break

            now_ts = time.time()
            prev = self._proc_cpu_state.get(pid)
            self._proc_cpu_state[pid] = (total_seconds, now_ts)
            if prev:
                prev_seconds, prev_ts = prev
                dt = max(1e-6, now_ts - prev_ts)
                cpu_delta = max(0.0, total_seconds - prev_seconds)
                # per-cpu percent approximation
                cpu_count = float(os.cpu_count() or 1)
                cpu_percent = (cpu_delta / dt) * 100.0 / cpu_count
                return cpu_percent, rss_kb
            return 0.0, rss_kb
        except Exception:
            return 0.0, 0

    async def _cleanup_stale_uploads(self) -> None:
        ttl = int(self.policy.get("uploadTtlSec", 600))
        while True:
            try:
                now_ts = time.time()
                stale: List[str] = []
                for upload_id, session in list(self.uploads.items()):
                    created = getattr(session, "created_ts", 0.0)
                    if created and (now_ts - created) > ttl:
                        stale.append(upload_id)

                for upload_id in stale:
                    session = self.uploads.pop(upload_id, None)
                    if session:
                        try:
                            os.remove(session.path)
                        except Exception:
                            pass
                        self.logger.info("removed stale upload %s", upload_id)
            except Exception as e:
                self.logger.error("cleanup_stale_uploads failed: %s", str(e))
            await asyncio.sleep(60)

    def _ros2_cmd(self, *subargs: str) -> List[str]:
        return [self.ros2_bin, *subargs]

    async def _collect_installed_packages(self, manager: str) -> Tuple[bool, List[str], str]:
        if manager == "opkg":
            rc, out, err = await self._run_command(["opkg", "list-installed"])
            if rc != 0:
                return False, [], err or "opkg unavailable"

            names: Set[str] = set()
            for raw in out.splitlines():
                line = raw.strip()
                if not line:
                    continue
                # opkg list-installed output: "name - version"
                pkg_name = line.split(" - ", 1)[0].strip()
                if pkg_name:
                    names.add(pkg_name)
            return True, sorted(list(names)), ""

        if manager == "pip":
            rc, out, err = await self._run_command(["pip3", "list", "--format=json"])
            if rc != 0:
                return False, [], err or "pip unavailable"

            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = []

            names = sorted(
                list(
                    {
                        str(item.get("name", "")).strip()
                        for item in parsed
                        if isinstance(item, dict) and str(item.get("name", "")).strip()
                    }
                )
            )
            return True, names, ""

        if manager == "ros":
            setup_bash = f"/opt/ros/{self.ros_distro}/setup.bash"
            workspace_root = str(self.policy.get("rosWorkspaceRoot", "/home/root/spiny_ws")).strip()
            user_ws_setup = os.path.join(workspace_root, "install", "setup.bash")

            source_cmd = f"source {setup_bash}"
            if os.path.exists(user_ws_setup):
                source_cmd += f" && source {user_ws_setup}"

            rc, out, err = await self._run_command(["/bin/bash", "-c", f"{source_cmd} && ros2 pkg list"])
            if rc != 0:
                return False, [], err or "ros2 pkg list failed"

            names = sorted(list({line.strip() for line in out.splitlines() if line.strip()}))
            return True, names, ""

        return False, [], "unsupported manager"

    async def _expose_external_library_dir(
        self,
        external_lib_dir: str,
        workspace_install_root: str,
    ) -> Tuple[bool, str, List[str]]:
        warnings: List[str] = []

        try:
            pathlib.Path(external_lib_dir).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"failed to create external lib dir: {exc}", warnings

        ld_conf_path = str(self.policy.get("ldSoConfFile", "/etc/ld.so.conf.d/spiny-external.conf")).strip()
        if not ld_conf_path:
            ld_conf_path = "/etc/ld.so.conf.d/spiny-external.conf"

        try:
            pathlib.Path(os.path.dirname(ld_conf_path)).mkdir(parents=True, exist_ok=True)
            with open(ld_conf_path, "w", encoding="utf-8") as handle:
                handle.write(f"{external_lib_dir}\n")
        except Exception as exc:
            return False, f"failed to write {ld_conf_path}: {exc}", warnings

        profile_path = "/etc/profile.d/spiny-external-libs.sh"
        profile_lines = [
            "#!/bin/sh",
            f'export LD_LIBRARY_PATH="{external_lib_dir}:{workspace_install_root}/lib:{workspace_install_root}/lib64:${{LD_LIBRARY_PATH}}"',
            "",
        ]
        try:
            with open(profile_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(profile_lines))
            os.chmod(profile_path, 0o755)
        except Exception as exc:
            warnings.append(f"failed to write {profile_path}: {exc}")

        ws_profile_path = "/etc/profile.d/spiny-ros-workspace.sh"
        ws_profile_lines = [
            "#!/bin/sh",
            f'if [ -f "/opt/ros/{self.ros_distro}/setup.sh" ]; then . "/opt/ros/{self.ros_distro}/setup.sh"; fi',
            f'if [ -f "{workspace_install_root}/setup.sh" ]; then . "{workspace_install_root}/setup.sh"; fi',
            "",
        ]
        try:
            with open(ws_profile_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(ws_profile_lines))
            os.chmod(ws_profile_path, 0o755)
        except Exception as exc:
            warnings.append(f"failed to write {ws_profile_path}: {exc}")

        if shutil.which("ldconfig"):
            rc, out, err = await self._run_command(["ldconfig"])
            if rc != 0:
                warnings.append(err or out or "ldconfig failed")
        else:
            warnings.append("ldconfig not found; runtime linker cache not refreshed")

        return True, "", warnings

    async def _install_ros_archive_bundle(
        self,
        archive_path: str,
        workspace_root: str,
        external_lib_dir: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if not os.path.exists(archive_path):
            return False, "archive file not found", {}

        install_root = os.path.join(workspace_root, "install")
        extract_root = os.path.join(self.upload_dir, f"ros-bundle-{uuid.uuid4()}")

        try:
            pathlib.Path(extract_root).mkdir(parents=True, exist_ok=True)
            pathlib.Path(install_root).mkdir(parents=True, exist_ok=True)
            pathlib.Path(external_lib_dir).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"failed to prepare directories: {exc}", {}

        rc_extract, out_extract, err_extract = await self._run_command(["tar", "-xf", archive_path, "-C", extract_root])
        if rc_extract != 0:
            shutil.rmtree(extract_root, ignore_errors=True)
            return False, err_extract or out_extract or "failed to extract archive", {}

        source_root = os.path.join(extract_root, "install")
        if not os.path.isdir(source_root):
            source_root = extract_root

        try:
            for name in os.listdir(source_root):
                src = os.path.join(source_root, name)
                dst = os.path.join(install_root, name)
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
                else:
                    if os.path.lexists(dst):
                        if os.path.isdir(dst) and not os.path.islink(dst):
                            shutil.rmtree(dst)
                        else:
                            os.unlink(dst)

                    if os.path.islink(src):
                        os.symlink(os.readlink(src), dst)
                    else:
                        shutil.copy2(src, dst, follow_symlinks=False)
        except Exception as exc:
            shutil.rmtree(extract_root, ignore_errors=True)
            return False, f"failed to deploy archive content: {exc}", {}

        copied_libs = 0
        warnings: List[str] = []
        lib_roots = [os.path.join(install_root, "lib"), os.path.join(install_root, "lib64")]
        try:
            for lib_root in lib_roots:
                if not os.path.isdir(lib_root):
                    continue

                for root, _, files in os.walk(lib_root):
                    for file_name in files:
                        if ".so" not in file_name:
                            continue

                        src_file = os.path.join(root, file_name)
                        dst_file = os.path.join(external_lib_dir, file_name)
                        if os.path.lexists(dst_file):
                            os.unlink(dst_file)

                        if os.path.islink(src_file):
                            os.symlink(os.readlink(src_file), dst_file)
                        else:
                            shutil.copy2(src_file, dst_file, follow_symlinks=False)
                        copied_libs += 1
        except Exception as exc:
            shutil.rmtree(extract_root, ignore_errors=True)
            return False, f"failed to export shared libraries: {exc}", {}

        ok_visibility, visibility_err, visibility_warnings = await self._expose_external_library_dir(
            external_lib_dir,
            install_root,
        )
        warnings.extend(visibility_warnings)
        if not ok_visibility:
            shutil.rmtree(extract_root, ignore_errors=True)
            return False, visibility_err, {}

        shutil.rmtree(extract_root, ignore_errors=True)
        return True, "installed", {
            "workspaceRoot": workspace_root,
            "installRoot": install_root,
            "externalLibDir": external_lib_dir,
            "sharedLibraryCount": copied_libs,
            "warnings": warnings,
        }

    async def _run_peer_command(
        self,
        peer_url: str,
        peer_token: str,
        action: str,
        payload: Dict[str, Any],
        timeout_sec: int,
    ) -> Dict[str, Any]:
        request_id = str(uuid.uuid4())
        request = {
            "v": 1,
            "type": "command",
            "action": action,
            "requestId": request_id,
            "payload": payload,
        }

        url = peer_url
        if peer_token:
            parsed = urllib.parse.urlparse(peer_url)
            query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            query.append(("token", peer_token))
            parsed = parsed._replace(query=urllib.parse.urlencode(query))
            url = urllib.parse.urlunparse(parsed)

        async with websockets.connect(url, max_size=None, ping_interval=20, ping_timeout=20) as websocket:
            await websocket.send(json.dumps(request, separators=(",", ":")))

            while True:
                raw = await asyncio.wait_for(websocket.recv(), timeout=max(1, timeout_sec))
                message = json.loads(raw)

                msg_request_id = message.get("requestId")
                if msg_request_id is None and message.get("action") == "connect":
                    return message

                if msg_request_id != request_id:
                    continue

                if message.get("type") == "ack":
                    continue

                return message

    def _peer_action_allowed(self, peer_cfg: Dict[str, Any], action: str) -> bool:
        allowed_actions = peer_cfg.get("allowedActions", [])
        if not isinstance(allowed_actions, list) or not allowed_actions:
            return False
        return action in allowed_actions

    async def _handle_peer_list(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        del payload
        peers: List[Dict[str, Any]] = []
        for peer_id in sorted(self.peers.keys()):
            cfg = self.peers[peer_id]
            peers.append(
                {
                    "peerId": peer_id,
                    "url": cfg.get("url", ""),
                    "allowRemoteControl": bool(cfg.get("allowRemoteControl", False)),
                    "allowedActions": list(cfg.get("allowedActions", [])),
                }
            )

        await self.send_message(
            websocket,
            "event",
            "peer.list",
            request_id,
            role,
            {
                "result": "success",
                "peerCount": len(peers),
                "peers": peers,
            },
        )

    async def _handle_peer_node_action(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        action: str,
        payload: Dict[str, Any],
    ) -> None:
        peer_action_map = {
            "peer.node.status": "node.status",
            "peer.node.start": "node.start",
            "peer.node.stop": "node.stop",
            "peer.node.restart": "node.restart",
        }
        delegated_action = peer_action_map[action]

        peer_id = payload.get("peerId")
        node_id = payload.get("nodeId")
        timeout_sec = payload.get("timeoutSec", 15)

        if not isinstance(peer_id, str) or not peer_id:
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "peerId is required",
                False,
            )
            return

        if action in {"peer.node.start", "peer.node.stop", "peer.node.restart"} and (
            not isinstance(node_id, str) or not node_id
        ):
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "nodeId is required for start/stop/restart",
                False,
            )
            return

        peer_cfg = self.peers.get(peer_id)
        if not peer_cfg:
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "PEER_NOT_FOUND",
                "peer not found in allowlist",
                False,
            )
            return

        if not bool(peer_cfg.get("allowRemoteControl", False)):
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "PEER_CONTROL_DISABLED",
                "remote control disabled for this peer",
                False,
            )
            return

        if not self._peer_action_allowed(peer_cfg, delegated_action):
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "PEER_ACTION_DENIED",
                "peer policy denied delegated action",
                False,
            )
            return

        try:
            timeout_value = int(timeout_sec)
        except (TypeError, ValueError):
            timeout_value = 15
        timeout_value = min(max(timeout_value, 1), 120)

        delegated_payload: Dict[str, Any] = {}
        if isinstance(node_id, str) and node_id:
            delegated_payload["nodeId"] = node_id
        if action == "peer.node.stop":
            grace = payload.get("graceSec", 5)
            if not isinstance(grace, int):
                grace = 5
            delegated_payload["graceSec"] = max(1, grace)

        try:
            message = await self._run_peer_command(
                peer_url=str(peer_cfg.get("url", "")),
                peer_token=str(peer_cfg.get("token", "")),
                action=delegated_action,
                payload=delegated_payload,
                timeout_sec=timeout_value,
            )
        except Exception as exc:
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "PEER_UNREACHABLE",
                str(exc),
                True,
                details={"peerId": peer_id, "delegatedAction": delegated_action},
            )
            return

        msg_type = message.get("type")
        if msg_type == "error":
            peer_payload = message.get("payload", {})
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                str(peer_payload.get("errorCode", "PEER_OPERATION_FAILED")),
                str(peer_payload.get("message", "remote peer returned error")),
                bool(peer_payload.get("retryable", False)),
                details={
                    "peerId": peer_id,
                    "delegatedAction": delegated_action,
                    "peerPayload": peer_payload,
                },
            )
            return

        await self.send_message(
            websocket,
            "event",
            action,
            request_id,
            role,
            {
                "result": "success",
                "peerId": peer_id,
                "delegatedAction": delegated_action,
                "peerResponse": message.get("payload", {}),
            },
        )

    async def _handle_user_info(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        del payload
        permissions = sorted(list(ROLE_PERMISSIONS.get(role, set())))
        await self.send_message(
            websocket,
            "event",
            "user.info",
            request_id,
            role,
            {
                "result": "success",
                "role": role,
                "permissions": permissions,
                "deviceId": self.device_id,
            },
        )

    def _normalize_ros2_node_name(self, node_name: str) -> str:
        cleaned = node_name.strip()
        if not cleaned:
            return ""
        if not cleaned.startswith("/"):
            cleaned = "/" + cleaned
        return cleaned

    def _resolve_runtime_ros2_node_name(self, node_id: str) -> str:
        config = self.managed_nodes.get(node_id, {})
        ros2_cfg = config.get("ros2") if isinstance(config.get("ros2"), dict) else {}
        if not isinstance(ros2_cfg, dict):
            return ""

        node_name = ros2_cfg.get("node_name")
        if not isinstance(node_name, str) or not node_name.strip():
            return ""

        namespace = ros2_cfg.get("namespace")
        node_base = node_name.strip().lstrip("/")
        if isinstance(namespace, str) and namespace.strip() and namespace.strip() != "/":
            ns = namespace.strip().rstrip("/")
            return self._normalize_ros2_node_name(f"{ns}/{node_base}")
        return self._normalize_ros2_node_name(node_base)

    def _parse_lifecycle_state(self, output: str) -> str:
        for raw in output.splitlines():
            line = raw.strip()
            if not line:
                continue
            state = line.split("[", 1)[0].strip().lower()
            if state:
                return state
        return "unknown"

    async def _ros2_lifecycle_get(self, node_name: str) -> Tuple[bool, str]:
        rc, out, err = await self._run_command(self._ros2_cmd("lifecycle", "get", node_name))
        if rc != 0:
            return False, err or out or "lifecycle get failed"
        return True, self._parse_lifecycle_state(out)

    async def _ros2_lifecycle_set(self, node_name: str, transition: str) -> Tuple[bool, str]:
        rc, out, err = await self._run_command(self._ros2_cmd("lifecycle", "set", node_name, transition))
        if rc != 0:
            return False, err or out or f"lifecycle set {transition} failed"
        return True, out.strip() or "ok"

    async def _wait_for_ros2_node_visible(self, node_name: str, timeout_sec: int = 12) -> bool:
        deadline = asyncio.get_running_loop().time() + max(1, timeout_sec)
        expected = self._normalize_ros2_node_name(node_name)

        while asyncio.get_running_loop().time() <= deadline:
            rc, out, _ = await self._run_command(self._ros2_cmd("node", "list"))
            if rc == 0:
                discovered = {
                    self._normalize_ros2_node_name(line)
                    for line in out.splitlines()
                    if line.strip()
                }
                if expected in discovered:
                    return True
            await asyncio.sleep(0.5)
        return False

    async def _terminate_process(
        self,
        process: asyncio.subprocess.Process,
        grace_sec: int,
    ) -> Tuple[bool, str]:
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=max(1, grace_sec))
            return True, "stopped"
        except asyncio.TimeoutError:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
                return True, "killed"
            except asyncio.TimeoutError:
                return False, "node did not stop"
        except ProcessLookupError:
            return True, "already exited"

    def _parse_typed_resource_lines(self, output: str) -> List[Dict[str, str]]:
        parsed: List[Dict[str, str]] = []
        for raw in output.splitlines():
            line = raw.strip()
            if not line:
                continue
            match = re.match(r"^(?P<name>\S+)\s*\[(?P<type>[^\]]+)\]$", line)
            if match:
                parsed.append({
                    "name": match.group("name"),
                    "type": match.group("type").strip(),
                })
            else:
                parsed.append({"name": line, "type": ""})
        return parsed

    async def _collect_graph_snapshot(self) -> Tuple[bool, Dict[str, Any], str]:
        warnings: List[str] = []
        graph: Dict[str, Any] = {
            "nodes": [],
            "topics": [],
            "services": [],
            "actions": [],
        }

        # Prefer rclpy-based inspection to avoid CLI overhead when available
        if self._rclpy_available:
            # lazy init of rclpy node to avoid side-effects during __init__
            if self._rclpy_node is None:
                try:
                    import rclpy
                    from rclpy.node import Node

                    rclpy.init(args=None)
                    try:
                        # prefer helper if available
                        create_node = getattr(rclpy, "create_node", None)
                        if callable(create_node):
                            self._rclpy_node = create_node("spiny_orchestrator_probe")
                        else:
                            self._rclpy_node = Node("spiny_orchestrator_probe")
                    except Exception:
                        self._rclpy_node = None
                except Exception as exc:
                    warnings.append(f"rclpy init failed: {exc}")

            if self._rclpy_node is not None:
                try:
                    # spin once to refresh discovery information so lists aren't stale
                    try:
                        await asyncio.to_thread(rclpy.spin_once, self._rclpy_node, 0.1)
                    except Exception:
                        pass
                    topics = await asyncio.to_thread(self._rclpy_node.get_topic_names_and_types)
                    services = await asyncio.to_thread(self._rclpy_node.get_service_names_and_types)
                    # node listing may be available as get_node_names_and_namespaces
                    try:
                        nodes = await asyncio.to_thread(self._rclpy_node.get_node_names_and_namespaces)
                        node_list = [name for name, ns in nodes]
                    except Exception:
                        node_list = []

                    graph["nodes"] = node_list
                    graph["topics"] = [
                        {"name": name, "type": (types[0] if types else "")} for name, types in topics
                    ]
                    graph["services"] = [
                        {"name": name, "type": (types[0] if types else "")} for name, types in services
                    ]
                    graph["actions"] = []
                    return True, {"graph": graph, "warnings": warnings}, ""
                except Exception as exc:
                    warnings.append(f"rclpy probe failed: {exc}")

        rc_nodes, out_nodes, err_nodes = await self._run_command(self._ros2_cmd("node", "list"))
        if rc_nodes != 0:
            return False, graph, err_nodes or "ros2 node list failed"
        graph["nodes"] = [line.strip() for line in out_nodes.splitlines() if line.strip()]

        rc_topics, out_topics, err_topics = await self._run_command(self._ros2_cmd("topic", "list", "-t"))
        if rc_topics == 0:
            graph["topics"] = self._parse_typed_resource_lines(out_topics)
        else:
            warnings.append(err_topics or "ros2 topic list failed")

        rc_services, out_services, err_services = await self._run_command(self._ros2_cmd("service", "list", "-t"))
        if rc_services == 0:
            graph["services"] = self._parse_typed_resource_lines(out_services)
        else:
            warnings.append(err_services or "ros2 service list failed")

        rc_actions, out_actions, err_actions = await self._run_command(self._ros2_cmd("action", "list", "-t"))
        if rc_actions == 0:
            graph["actions"] = self._parse_typed_resource_lines(out_actions)
        else:
            warnings.append(err_actions or "ros2 action list failed")

        return True, {"graph": graph, "warnings": warnings}, ""

    def _resolve_node_io_target(self, payload: Dict[str, Any]) -> Optional[str]:
        node_name = payload.get("nodeName")
        if isinstance(node_name, str) and node_name.strip():
            return node_name.strip()

        node_id = payload.get("nodeId")
        if isinstance(node_id, str) and node_id in self.managed_nodes:
            resolved = self._resolve_runtime_ros2_node_name(node_id)
            if resolved:
                return resolved
            return node_id

        return None

    def _parse_node_info_output(self, output: str) -> Dict[str, Any]:
        section_map = {
            "Subscribers": "subscribers",
            "Publishers": "publishers",
            "Service Servers": "serviceServers",
            "Service Clients": "serviceClients",
            "Action Servers": "actionServers",
            "Action Clients": "actionClients",
        }

        parsed: Dict[str, Any] = {
            "nodeName": "",
            "nodeNamespace": "",
            "subscribers": [],
            "publishers": [],
            "serviceServers": [],
            "serviceClients": [],
            "actionServers": [],
            "actionClients": [],
        }

        current_section = ""
        for raw in output.splitlines():
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("Node name:"):
                parsed["nodeName"] = stripped.split(":", 1)[1].strip()
                continue
            if stripped.startswith("Node namespace:"):
                parsed["nodeNamespace"] = stripped.split(":", 1)[1].strip()
                continue

            if stripped.endswith(":"):
                title = stripped[:-1]
                current_section = section_map.get(title, "")
                continue

            if not current_section:
                continue

            item_match = re.match(r"^([^:]+):\s*(.+)$", stripped)
            if not item_match:
                continue

            parsed[current_section].append(
                {
                    "name": item_match.group(1).strip(),
                    "type": item_match.group(2).strip(),
                }
            )

        return parsed

    async def _handle_graph_snapshot(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        del payload
        await self._reap_finished_nodes()

        ok, graph_payload, err = await self._collect_graph_snapshot()
        if not ok:
            await self.send_error(
                websocket,
                "graph.snapshot",
                request_id,
                role,
                "ROS2_GRAPH_FAILED",
                err,
                True,
            )
            return

        managed = [self._node_snapshot(node_id) for node_id in sorted(self.managed_nodes.keys())]
        await self.send_message(
            websocket,
            "event",
            "graph.snapshot",
            request_id,
            role,
            {
                "result": "success",
                "graph": graph_payload["graph"],
                "warnings": graph_payload.get("warnings", []),
                "managedNodes": managed,
            },
        )

    async def _handle_node_io_inspect(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        target = self._resolve_node_io_target(payload)
        if not target:
            await self.send_error(
                websocket,
                "node.io.inspect",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "nodeName or valid nodeId is required",
                False,
            )
            return

        rc, out, err = await self._run_command(self._ros2_cmd("node", "info", target))
        if rc != 0:
            await self.send_error(
                websocket,
                "node.io.inspect",
                request_id,
                role,
                "ROS2_NODE_INFO_FAILED",
                err or f"failed to inspect {target}",
                True,
                details={"nodeName": target},
            )
            return

        parsed = self._parse_node_info_output(out)
        if not parsed.get("nodeName"):
            parsed["nodeName"] = target

        await self.send_message(
            websocket,
            "event",
            "node.io.inspect",
            request_id,
            role,
            {
                "result": "success",
                "requestedNode": target,
                "io": parsed,
            },
        )

    async def _collect_node_info_best_effort(self, node_name: str) -> Tuple[Optional[Dict[str, Any]], str]:
        rc, out, err = await self._run_command(self._ros2_cmd("node", "info", node_name))
        if rc != 0:
            return None, err or f"failed to inspect {node_name}"

        parsed = self._parse_node_info_output(out)
        if not parsed.get("nodeName"):
            parsed["nodeName"] = node_name
        return parsed, ""

    async def _stream_sample_for_node(self, node_id: str, fields: List[str], interval_sec: float) -> Dict[str, Any]:
        snapshot = self._node_snapshot(node_id)
        pid = snapshot.get("pid")

        cpu_percent = 0.0
        mem_rss_kb = 0
        if isinstance(pid, int):
            cpu_percent, mem_rss_kb = await self._sample_process_metrics(pid, interval_sec)

        if not fields:
            return {
                "running": snapshot.get("running"),
                "pid": pid,
                "startedAt": snapshot.get("startedAt"),
                "ros2State": snapshot.get("ros2State"),
                "cpuPercent": cpu_percent,
                "memoryRssKb": mem_rss_kb,
            }

        sample: Dict[str, Any] = {}
        for field in fields:
            if field in snapshot:
                sample[field] = snapshot[field]
            elif field == "cpuPercent":
                sample["cpuPercent"] = cpu_percent
            elif field == "memoryRssKb":
                sample["memoryRssKb"] = mem_rss_kb
        return sample

    async def _stream_subscription_loop(self, subscription_id: str) -> None:
        while True:
            subscription = self.stream_subscriptions.get(subscription_id)
            if not subscription:
                return

            await self._reap_finished_nodes()
            sample = await self._stream_sample_for_node(
                subscription.node_id, subscription.fields, subscription.interval_sec
            )

            try:
                await self.send_message(
                    subscription.websocket,
                    "event",
                    "stream.data",
                    None,
                    subscription.role,
                    {
                        "subscriptionId": subscription_id,
                        "nodeId": subscription.node_id,
                        "ts": utc_now(),
                        "data": sample,
                    },
                )
            except Exception:
                self._remove_subscription(subscription_id)
                return

            await asyncio.sleep(max(0.1, subscription.interval_sec))

    def _remove_subscription(self, subscription_id: str) -> None:
        subscription = self.stream_subscriptions.pop(subscription_id, None)
        if not subscription:
            return

        conn_key = id(subscription.websocket)
        active = self.connection_subscriptions.get(conn_key, set())
        if subscription_id in active:
            active.remove(subscription_id)
        if not active and conn_key in self.connection_subscriptions:
            self.connection_subscriptions.pop(conn_key, None)

        if not subscription.task.done():
            subscription.task.cancel()

    def _cleanup_connection_subscriptions(self, websocket: websockets.WebSocketServerProtocol) -> None:
        conn_key = id(websocket)
        subscription_ids = list(self.connection_subscriptions.get(conn_key, set()))
        for subscription_id in subscription_ids:
            self._remove_subscription(subscription_id)
        self.connection_subscriptions.pop(conn_key, None)

    async def _handle_stream_subscribe(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        node_id = payload.get("nodeId")
        fields_raw = payload.get("fields", [])
        rate_hz = payload.get("rateHz", 1.0)

        if not isinstance(node_id, str) or node_id not in self.managed_nodes:
            await self.send_error(
                websocket,
                "stream.subscribe",
                request_id,
                role,
                "NODE_NOT_FOUND",
                "nodeId must reference a managed node",
                False,
            )
            return

        if not isinstance(fields_raw, list):
            fields_raw = []
        fields = [str(item).strip() for item in fields_raw if isinstance(item, str) and item.strip()]

        try:
            rate_value = float(rate_hz)
        except (TypeError, ValueError):
            rate_value = 1.0
        rate_value = min(max(rate_value, 0.2), 20.0)
        interval_sec = 1.0 / rate_value

        subscription_id = str(uuid.uuid4())
        task = asyncio.create_task(self._stream_subscription_loop(subscription_id))
        subscription = StreamSubscription(
            subscription_id=subscription_id,
            node_id=node_id,
            fields=fields,
            interval_sec=interval_sec,
            websocket=websocket,
            role=role,
            task=task,
        )
        self.stream_subscriptions[subscription_id] = subscription
        self.connection_subscriptions.setdefault(id(websocket), set()).add(subscription_id)

        await self.send_message(
            websocket,
            "event",
            "stream.subscribe",
            request_id,
            role,
            {
                "result": "success",
                "subscriptionId": subscription_id,
                "nodeId": node_id,
                "fields": fields,
                "rateHz": rate_value,
            },
        )

    async def _handle_stream_unsubscribe(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        subscription_id = payload.get("subscriptionId")
        if not isinstance(subscription_id, str) or not subscription_id:
            await self.send_error(
                websocket,
                "stream.unsubscribe",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "subscriptionId is required",
                False,
            )
            return

        subscription = self.stream_subscriptions.get(subscription_id)
        if not subscription:
            await self.send_error(
                websocket,
                "stream.unsubscribe",
                request_id,
                role,
                "STREAM_NOT_FOUND",
                "subscription not found",
                False,
            )
            return

        if subscription.websocket is not websocket:
            await self.send_error(
                websocket,
                "stream.unsubscribe",
                request_id,
                role,
                "WS_AUTH_FORBIDDEN_ROLE",
                "subscription belongs to another session",
                False,
            )
            return

        self._remove_subscription(subscription_id)

        await self.send_message(
            websocket,
            "event",
            "stream.unsubscribe",
            request_id,
            role,
            {
                "result": "success",
                "subscriptionId": subscription_id,
                "unsubscribed": True,
            },
        )

    async def _handle_orchestrator_reload(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        del payload
        self.logger.info("reloading manifest and policy from disk (requestId=%s)", request_id)
        
        # Refresh configuration from disk
        self.policy = self._load_policy()
        self.managed_nodes = self._load_manifest_nodes()
        self.peers = self._load_peers()
        
        # Trigger reconciliation to start/stop nodes as per new manifest
        asyncio.create_task(self._reconcile_nodes())
        
        await self.send_message(
            websocket,
            "event",
            "orchestrator.reload",
            request_id,
            role,
            {
                "result": "success",
                "message": "orchestrator configuration reloaded",
                "nodeCount": len(self.managed_nodes),
                "peerCount": len(self.peers),
            },
        )

    async def _handle_capture_window(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        duration_sec = payload.get("durationSec", 5)
        sample_interval_sec = payload.get("sampleIntervalSec", 1)
        node_names_raw = payload.get("nodeNames", [])

        if not isinstance(duration_sec, int):
            duration_sec = 5
        if not isinstance(sample_interval_sec, int):
            sample_interval_sec = 1
        duration_sec = min(max(duration_sec, 1), 60)
        sample_interval_sec = min(max(sample_interval_sec, 1), 10)

        node_names: List[str] = []
        if isinstance(node_names_raw, list):
            node_names = [str(item).strip() for item in node_names_raw if isinstance(item, str) and item.strip()]

        capture_id = str(uuid.uuid4())
        started_at = utc_now()

        await self.send_message(
            websocket,
            "ack",
            "capture.window",
            request_id,
            role,
            {
                "captureId": capture_id,
                "state": "accepted",
                "durationSec": duration_sec,
                "sampleIntervalSec": sample_interval_sec,
            },
        )

        samples: List[Dict[str, Any]] = []
        warnings: List[str] = []
        total_samples = max(1, duration_sec // sample_interval_sec)

        for idx in range(total_samples):
            ok_graph, graph_payload, graph_err = await self._collect_graph_snapshot()
            if not ok_graph:
                await self.send_error(
                    websocket,
                    "capture.window",
                    request_id,
                    role,
                    "ROS2_GRAPH_FAILED",
                    graph_err,
                    True,
                    details={"captureId": capture_id},
                )
                return

            sample: Dict[str, Any] = {
                "ts": utc_now(),
                "graph": graph_payload.get("graph", {}),
                "graphWarnings": graph_payload.get("warnings", []),
            }
            warnings.extend([str(item) for item in graph_payload.get("warnings", [])])

            if node_names:
                io_items: List[Dict[str, Any]] = []
                for node_name in node_names:
                    parsed, node_err = await self._collect_node_info_best_effort(node_name)
                    if parsed is not None:
                        io_items.append(parsed)
                    elif node_err:
                        warnings.append(f"{node_name}: {node_err}")
                sample["nodeIo"] = io_items

            samples.append(sample)

            percent = int(((idx + 1) / total_samples) * 100)
            await self.send_message(
                websocket,
                "progress",
                "capture.window",
                request_id,
                role,
                {
                    "captureId": capture_id,
                    "phase": "capture",
                    "percent": percent,
                    "message": f"collected {idx + 1}/{total_samples} samples",
                },
            )

            if idx + 1 < total_samples:
                await asyncio.sleep(sample_interval_sec)

        artifact = {
            "captureId": capture_id,
            "startedAt": started_at,
            "endedAt": utc_now(),
            "durationSec": duration_sec,
            "sampleIntervalSec": sample_interval_sec,
            "sampleCount": len(samples),
            "warnings": warnings,
            "samples": samples,
        }

        artifact_path = os.path.join(self.capture_dir, f"capture-{capture_id}.json")
        with open(artifact_path, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2, ensure_ascii=True)

        await self.send_message(
            websocket,
            "event",
            "capture.window",
            request_id,
            role,
            {
                "result": "success",
                "captureId": capture_id,
                "artifactPath": artifact_path,
                "sampleCount": len(samples),
                "warnings": warnings,
            },
        )

    def _is_url_package(self, package_name: str) -> bool:
        return "://" in package_name

    def _policy_allows_urls(self, source_policy: str) -> bool:
        if source_policy == "allow-url":
            return bool(self.policy.get("allowUrl", False))
        return False

    def _extract_domain(self, value: str) -> str:
        try:
            parsed = urllib.parse.urlparse(value)
        except Exception:
            return ""
        return (parsed.hostname or "").lower()

    def _domain_allowed(self, value: str) -> bool:
        host = self._extract_domain(value)
        if not host:
            return False

        domains = self.policy.get("allowedDomains", [])
        normalized = [str(item).lower().strip() for item in domains if str(item).strip()]
        if not normalized:
            return False

        for domain in normalized:
            if host == domain or host.endswith("." + domain):
                return True
        return False

    def _is_blocked(self, package_name: str) -> bool:
        blocked = self.policy.get("blockedPackages", [])
        return package_name in blocked

    def _pip_binary_only(self) -> bool:
        return bool(self.policy.get("pipBinaryOnly", True))

    async def _attempt_rollback(self, manager: str, packages: List[str]) -> Tuple[bool, str, str]:
        if not bool(self.policy.get("enableRollback", True)):
            return True, "rollback skipped by policy", ""

        rollback_candidates = [p for p in packages if "://" not in p]
        if not rollback_candidates:
            return True, "rollback skipped for URL-based packages", ""

        if manager == "opkg":
            cmd = ["opkg", "remove"] + rollback_candidates
        else:
            cmd = ["pip3", "uninstall", "-y"] + rollback_candidates

        rc, out, err = await self._run_command(cmd)
        return rc == 0, out, err

    async def _reap_finished_nodes(self) -> None:
        finished: List[Tuple[str, Optional[int]]] = []
        for node_id, runtime in list(self.node_runtimes.items()):
            try:
                rc = runtime.process.returncode
            except Exception:
                rc = None
            if rc is not None:
                finished.append((node_id, rc))

        for node_id, returncode in finished:
            config = self.managed_nodes.get(node_id, {}) if isinstance(self.managed_nodes, dict) else {}
            restart_policy = str(config.get("restart_policy", "no")).lower()
            should_restart = False
            if restart_policy == "always":
                should_restart = True
            elif restart_policy == "on-failure" and (returncode or 0) != 0:
                should_restart = True

            if should_restart:
                # simple rate limiting: allow up to 5 restarts per 60s window
                count, first_ts = self._node_restart_info.get(node_id, (0, 0.0))
                now_ts = time.time()
                if now_ts - first_ts > 60:
                    count = 0
                    first_ts = now_ts
                count += 1
                self._node_restart_info[node_id] = (count, first_ts)
                if count <= 5:
                    self.logger.warning(
                        "node %s exited (rc=%s); restarting (policy=%s) attempt=%d",
                        node_id,
                        str(returncode),
                        restart_policy,
                        count,
                    )
                    ok, msg = await self._start_managed_node(node_id)
                    if not ok:
                        self.logger.error("failed to restart node %s: %s", node_id, msg)
                    continue
                else:
                    self.logger.error(
                        "node %s restarted %d times within window; not restarting",
                        node_id,
                        count,
                    )

                # remove runtime record if not restarted
                runtime = self.node_runtimes.pop(node_id, None)
                if runtime:
                    try:
                        pid = runtime.process.pid
                        if isinstance(pid, int):
                            self._proc_cpu_state.pop(pid, None)
                    except Exception:
                        pass

                self._node_restart_info.pop(node_id, None)

    def _node_snapshot(self, node_id: str) -> Dict[str, Any]:
        config = self.managed_nodes[node_id]
        runtime = self.node_runtimes.get(node_id)

        running = bool(runtime and runtime.process.returncode is None)
        ros2_cfg = config.get("ros2") if isinstance(config.get("ros2"), dict) else None
        ros2_state = "inactive"
        lifecycle_mode = config.get("lifecycle_mode", "process")
        ros2_node_name = ""
        if runtime:
            lifecycle_mode = runtime.lifecycle_mode or lifecycle_mode
            ros2_node_name = runtime.ros2_node_name or ""
            if running:
                if runtime.lifecycle_mode == "managed":
                    ros2_state = runtime.lifecycle_state or "unknown"
                else:
                    ros2_state = "active"
        return {
            "nodeId": node_id,
            "configured": True,
            "running": running,
            "pid": runtime.process.pid if running and runtime else None,
            "startedAt": runtime.started_at if running and runtime else None,
            "mode": config.get("mode", "process"),
            "lifecycleMode": lifecycle_mode,
            "ros2State": ros2_state,
            "ros2NodeName": ros2_node_name,
            "start": config.get("start", []),
            "cwd": config.get("cwd") or "",
            "ros2": ros2_cfg,
        }

    async def _start_managed_node(self, node_id: str) -> Tuple[bool, str]:
        config = self.managed_nodes.get(node_id)
        if not config:
            return False, "node is not defined in manifest"

        runtime = self.node_runtimes.get(node_id)
        if runtime and runtime.process.returncode is None:
            return False, "node already running"

        cmd = config["start"]
        cwd = config.get("cwd") or None
        env = os.environ.copy()
        env.update(config.get("env", {}))
        if self.default_rmw.strip():
            env.setdefault("RMW_IMPLEMENTATION", self.default_rmw.strip())
        if self.default_ros_domain_id.strip():
            env.setdefault("ROS_DOMAIN_ID", self.default_ros_domain_id.strip())
        if self.default_ros_localhost_only.strip() in {"0", "1"}:
            env.setdefault("ROS_LOCALHOST_ONLY", self.default_ros_localhost_only.strip())

        lifecycle_mode = str(config.get("lifecycle_mode", "process"))
        ros2_node_name = self._resolve_runtime_ros2_node_name(node_id)

        # Wrap in shell to source ROS environment if it's a ROS 2 node
        final_cmd = cmd
        if config.get("mode") == "ros2":
            setup_path = f"/opt/ros/{self.ros_distro}/setup.bash"
            escaped_cmd = " ".join(shlex.quote(str(item)) for item in cmd)
            # We use bash to source and exec to keep PID management correct
            final_cmd = ["/bin/bash", "-c", f"source {setup_path} && exec {escaped_cmd}"]

        try:
            process = await asyncio.create_subprocess_exec(
                *final_cmd,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Non-blocking log capture (optional background task)
            asyncio.create_task(self._log_subprocess_output(node_id, process))
        except Exception as exc:
            return False, str(exc)

        self.node_runtimes[node_id] = NodeRuntime(
            node_id=node_id,
            process=process,
            started_at=utc_now(),
            start_cmd=[str(item) for item in cmd],
            ros2_node_name=ros2_node_name or None,
            lifecycle_mode=lifecycle_mode,
            lifecycle_state="starting",
        )

        runtime_record = self.node_runtimes[node_id]
        if lifecycle_mode != "managed":
            runtime_record.lifecycle_state = "active"
            self.logger.info("node %s started successfully (pid=%d)", node_id, process.pid)
            return True, "started"

        if not ros2_node_name:
            await self._terminate_process(process, grace_sec=3)
            self.node_runtimes.pop(node_id, None)
            return False, "managed lifecycle requires node_name in manifest"

        # Managed lifecycle logic stays in _start_managed_node
        visible = await self._wait_for_ros2_node_visible(ros2_node_name, timeout_sec=12)
        if not visible:
            await self._terminate_process(process, grace_sec=3)
            self.node_runtimes.pop(node_id, None)
            return False, f"ros2 node not discovered: {ros2_node_name}"

        ok_cfg, msg_cfg = await self._ros2_lifecycle_set(ros2_node_name, "configure")
        if not ok_cfg:
            await self._terminate_process(process, grace_sec=3)
            self.node_runtimes.pop(node_id, None)
            return False, f"configure failed: {msg_cfg}"

        ok_act, msg_act = await self._ros2_lifecycle_set(ros2_node_name, "activate")
        if not ok_act:
            await self._terminate_process(process, grace_sec=3)
            self.node_runtimes.pop(node_id, None)
            return False, f"activate failed: {msg_act}"

        ok_get, state_or_err = await self._ros2_lifecycle_get(ros2_node_name)
        runtime_record.lifecycle_state = state_or_err if ok_get else "active"
        return True, "started(managed)"

    async def _log_subprocess_output(self, node_id: str, process: asyncio.subprocess.Process) -> None:
        """Helper to pipe subprocess logs to the main orchestrator logs"""
        async def _drain(stream, log_fn, level_name: str):
            try:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    try:
                        log_fn("[%s] %s", node_id, line.decode("utf-8", errors="replace").strip())
                    except Exception:
                        log_fn("[%s] %s", node_id, str(line))
            except Exception as e:
                self.logger.error("[%s] logging %s failed: %s", node_id, level_name, str(e))

        tasks = []
        try:
            if process.stdout:
                tasks.append(asyncio.create_task(_drain(process.stdout, self.logger.info, "stdout")))
            if process.stderr:
                tasks.append(asyncio.create_task(_drain(process.stderr, self.logger.error, "stderr")))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.logger.error("[%s] logging task failed: %s", node_id, str(e))

    async def _stop_managed_node(self, node_id: str, grace_sec: int = 5) -> Tuple[bool, str]:
        runtime = self.node_runtimes.get(node_id)
        if not runtime or runtime.process.returncode is not None:
            self.node_runtimes.pop(node_id, None)
            return False, "node is not running"

        if runtime.lifecycle_mode == "managed" and runtime.ros2_node_name:
            await self._ros2_lifecycle_set(runtime.ros2_node_name, "deactivate")
            await self._ros2_lifecycle_set(runtime.ros2_node_name, "shutdown")
            runtime.lifecycle_state = "finalized"

        try:
            ok_stop, stop_msg = await self._terminate_process(runtime.process, grace_sec=grace_sec)
            if not ok_stop:
                return False, stop_msg
        finally:
            runtime = self.node_runtimes.pop(node_id, None)
            if runtime:
                try:
                    pid = runtime.process.pid
                    if isinstance(pid, int):
                        self._proc_cpu_state.pop(pid, None)
                except Exception:
                    pass

        return True, "stopped"

    def _create_operation(self, action: str, manager: str, packages: List[str]) -> Operation:
        op_id = str(uuid.uuid4())
        now = utc_now()
        op = Operation(
            operation_id=op_id,
            action=action,
            manager=manager,
            state="accepted",
            created_at=now,
            updated_at=now,
            packages=packages,
        )
        self.operations[op_id] = op
        return op

    async def _handle_pkg_list(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        manager = payload.get("manager", "opkg")
        ok, installed, err = await self._collect_installed_packages(manager)
        if not ok:
            await self.send_error(
                websocket,
                "pkg.list",
                request_id,
                role,
                "PKG_INSTALL_MANAGER_UNAVAILABLE",
                err,
                True,
            )
            return

        await self.send_message(
            websocket,
            "event",
            "pkg.list",
            request_id,
            role,
            {"result": "success", "installed": installed},
        )

    async def _handle_pkg_missing(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        manager = str(payload.get("manager", "opkg")).strip()
        required_raw = payload.get("requiredPackages", payload.get("packages", []))
        if not isinstance(required_raw, list):
            await self.send_error(
                websocket,
                "pkg.missing",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "requiredPackages must be list",
                False,
            )
            return

        required_packages = [str(item).strip() for item in required_raw if isinstance(item, str) and str(item).strip()]
        if not required_packages:
            await self.send_error(
                websocket,
                "pkg.missing",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "requiredPackages cannot be empty",
                False,
            )
            return

        ok, installed_packages, err = await self._collect_installed_packages(manager)
        if not ok:
            await self.send_error(
                websocket,
                "pkg.missing",
                request_id,
                role,
                "PKG_INSTALL_MANAGER_UNAVAILABLE",
                err,
                True,
            )
            return

        if manager == "pip":
            installed_lookup = {pkg.lower() for pkg in installed_packages}
            missing = sorted(list({pkg for pkg in required_packages if pkg.lower() not in installed_lookup}))
        else:
            installed_lookup = set(installed_packages)
            missing = sorted(list({pkg for pkg in required_packages if pkg not in installed_lookup}))

        await self.send_message(
            websocket,
            "event",
            "pkg.missing",
            request_id,
            role,
            {
                "result": "success",
                "manager": manager,
                "requiredPackages": sorted(list(set(required_packages))),
                "missingPackages": missing,
                "missingCount": len(missing),
                "installedCount": len(installed_packages),
            },
        )

    async def _handle_pkg_status(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        op_id = payload.get("operationId")
        if not isinstance(op_id, str):
            await self.send_error(
                websocket,
                "pkg.status",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "operationId is required",
                False,
            )
            return

        op = self.operations.get(op_id)
        if not op:
            await self.send_error(
                websocket,
                "pkg.status",
                request_id,
                role,
                "PKG_UPLOAD_NOT_FOUND",
                "operation not found",
                False,
                operation_id=op_id,
            )
            return

        await self.send_message(
            websocket,
            "event",
            "pkg.status",
            request_id,
            role,
            {
                "operationId": op.operation_id,
                "state": op.state,
                "manager": op.manager,
                "packages": op.packages,
                "result": op.result,
                "errorCode": op.error_code,
                "errorMessage": op.error_message,
                "updatedAt": op.updated_at,
            },
        )

    async def _handle_pkg_install(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        manager = payload.get("manager")
        packages = payload.get("packages")
        source_policy = payload.get("sourcePolicy", self.policy.get("defaultSourcePolicy", "repo-only"))

        if manager not in {"opkg", "pip", "ros"} or not isinstance(packages, list) or not packages:
            await self.send_error(
                websocket,
                "pkg.install",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "invalid manager or packages list",
                False,
            )
            return

        # Limit concurrent package operations globally
        if self.running_operations >= int(self.policy.get("maxParallelOps", 2)):
            await self.send_error(
                websocket,
                "pkg.install",
                request_id,
                role,
                "PKG_POLICY_LIMIT_EXCEEDED",
                "too many running package operations",
                True,
            )
            return

        if manager == "ros":
            archive_path = payload.get("archivePath") or payload.get("file")
            if not archive_path and packages:
                first = packages[0]
                if isinstance(first, str):
                    archive_path = first

            if not isinstance(archive_path, str) or not archive_path.strip():
                await self.send_error(
                    websocket,
                    "pkg.install",
                    request_id,
                    role,
                    "WS_SCHEMA_INVALID",
                    "archivePath (or file) is required for manager=ros",
                    False,
                )
                return

            workspace_root = str(
                payload.get("workspaceRoot")
                or self.policy.get("rosWorkspaceRoot", "/home/root/spiny_ws")
            ).strip()
            external_lib_dir = str(
                payload.get("externalLibDir")
                or self.policy.get("externalLibDir", "/opt/spiny/external/lib")
            ).strip()

            ok_ros, message_ros, details_ros = await self._install_ros_archive_bundle(
                archive_path=archive_path.strip(),
                workspace_root=workspace_root,
                external_lib_dir=external_lib_dir,
            )
            if not ok_ros:
                await self.send_error(
                    websocket,
                    "pkg.install",
                    request_id,
                    role,
                    "PKG_INSTALL_FAILED",
                    message_ros,
                    False,
                    details={
                        "manager": "ros",
                        "archivePath": archive_path.strip(),
                    },
                )
                return

            await self.send_message(
                websocket,
                "event",
                "pkg.install",
                request_id,
                role,
                {
                    "result": "success",
                    "manager": "ros",
                    "archivePath": archive_path.strip(),
                    "details": details_ros,
                },
            )
            return

        for package_name in packages:
            if self._is_blocked(str(package_name)):
                await self.send_error(
                    websocket,
                    "pkg.install",
                    request_id,
                    role,
                    "PKG_POLICY_DENIED_PACKAGE",
                    f"blocked package: {package_name}",
                    False,
                )
                return
            if self._is_url_package(str(package_name)) and not self._policy_allows_urls(str(source_policy)):
                await self.send_error(
                    websocket,
                    "pkg.install",
                    request_id,
                    role,
                    "PKG_POLICY_DENIED_SOURCE",
                    "URL source denied by policy",
                    False,
                )
                return
            if self._is_url_package(str(package_name)) and not self._domain_allowed(str(package_name)):
                await self.send_error(
                    websocket,
                    "pkg.install",
                    request_id,
                    role,
                    "PKG_POLICY_DENIED_SOURCE",
                    "source domain is not allowlisted",
                    False,
                )
                return

        op = self._create_operation("pkg.install", manager, [str(p) for p in packages])
        self.running_operations += 1

        try:
            await self.send_message(
                websocket,
                "ack",
                "pkg.install",
                request_id,
                role,
                {"operationId": op.operation_id, "state": "accepted", "etaSec": 0},
            )

            op.state = "running"
            op.updated_at = utc_now()
            await self.send_message(
                websocket,
                "progress",
                "pkg.install",
                request_id,
                role,
                {
                    "operationId": op.operation_id,
                    "phase": "install",
                    "percent": 10,
                    "message": "installation started",
                },
            )

            if manager == "opkg":
                cmd = ["opkg", "install"] + op.packages
            else:
                cmd = ["pip3", "install", "--no-input"]
                if self._pip_binary_only():
                    cmd += ["--only-binary", ":all:", "--prefer-binary"]
                cmd += op.packages

            rc, out, err = await self._run_command(cmd)

            if rc == 0:
                op.state = "done"
                op.result = "success"
                op.updated_at = utc_now()
                await self.send_message(
                    websocket,
                    "event",
                    "pkg.install",
                    request_id,
                    role,
                    {
                        "operationId": op.operation_id,
                        "result": "success",
                        "installed": op.packages,
                        "warnings": [],
                        "stdout": out,
                    },
                )
            else:
                op.state = "failed"
                await self.send_message(
                    websocket,
                    "progress",
                    "pkg.install",
                    request_id,
                    role,
                    {
                        "operationId": op.operation_id,
                        "phase": "rollback",
                        "percent": 90,
                        "message": "rolling back failed install",
                    },
                )

                rollback_ok, rollback_out, rollback_err = await self._attempt_rollback(manager, op.packages)

                if rollback_ok:
                    op.error_code = "PKG_INSTALL_DEPENDENCY_FAILED"
                    op.error_message = err or "installation failed"
                    details = {"stdout": out, "stderr": err, "rollback": rollback_out}
                else:
                    op.error_code = "PKG_INSTALL_ROLLBACK_FAILED"
                    op.error_message = rollback_err or "rollback failed"
                    details = {
                        "stdout": out,
                        "stderr": err,
                        "rollback_stdout": rollback_out,
                        "rollback_stderr": rollback_err,
                    }

                op.updated_at = utc_now()
                await self.send_error(
                    websocket,
                    "pkg.install",
                    request_id,
                    role,
                    op.error_code,
                    op.error_message,
                    False,
                    details=details,
                    operation_id=op.operation_id,
                )

        finally:
            self.running_operations = max(0, self.running_operations - 1)
            self.logger.info(
                "pkg.install requestId=%s operationId=%s manager=%s packages=%s state=%s",
                request_id,
                op.operation_id,
                manager,
                op.packages,
                op.state,
            )

    async def _handle_upload_begin(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        manager = payload.get("manager")
        artifact_type = payload.get("artifactType")
        file_name = payload.get("fileName")
        size_bytes = payload.get("sizeBytes")
        expected_sha = payload.get("sha256")
        target = payload.get("target", "install")

        allowed_artifacts = {
            "opkg": {"ipk"},
            "pip": {"whl"},
            "ros": {"tar", "tar.gz", "tgz"},
        }

        if (
            manager not in allowed_artifacts
            or artifact_type not in allowed_artifacts.get(str(manager), set())
            or not isinstance(file_name, str)
            or not isinstance(size_bytes, int)
            or not isinstance(expected_sha, str)
        ):
            await self.send_error(
                websocket,
                "pkg.upload.begin",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "invalid upload.begin payload",
                False,
            )
            return

        max_size = int(self.policy.get("maxUploadBytes", 104857600))
        if size_bytes > max_size:
            await self.send_error(
                websocket,
                "pkg.upload.begin",
                request_id,
                role,
                "PKG_POLICY_LIMIT_EXCEEDED",
                "artifact exceeds maxUploadBytes",
                True,
            )
            return

        upload_id = str(uuid.uuid4())
        clean_name = os.path.basename(file_name).lstrip(".")
        path = os.path.join(self.upload_dir, f"{upload_id}-{clean_name}")
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb"):
            pass

        self.uploads[upload_id] = UploadSession(
            upload_id=upload_id,
            manager=manager,
            artifact_type=artifact_type,
            file_name=file_name,
            size_bytes=size_bytes,
            sha256=expected_sha,
            target=target,
            expected_seq=0,
            bytes_received=0,
            path=path,
            created_ts=time.time(),
        )

        await self.send_message(
            websocket,
            "ack",
            "pkg.upload.begin",
            request_id,
            role,
            {
                "uploadId": upload_id,
                "state": "accepted",
                "maxChunkBytes": int(self.policy.get("maxChunkBytes", 262144)),
                "ttlSec": 600,
            },
        )

    async def _handle_upload_chunk(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        upload_id = payload.get("uploadId")
        seq = payload.get("seq")
        data = payload.get("data")
        chunk_sha = payload.get("chunkSha256")

        if not isinstance(upload_id, str) or not isinstance(seq, int) or not isinstance(data, str):
            await self.send_error(
                websocket,
                "pkg.upload.chunk",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "invalid upload.chunk payload",
                False,
            )
            return

        session = self.uploads.get(upload_id)
        if not session:
            await self.send_error(
                websocket,
                "pkg.upload.chunk",
                request_id,
                role,
                "PKG_UPLOAD_NOT_FOUND",
                "upload session not found",
                False,
            )
            return

        if seq != session.expected_seq:
            await self.send_error(
                websocket,
                "pkg.upload.chunk",
                request_id,
                role,
                "PKG_UPLOAD_CHUNK_OUT_OF_ORDER",
                "chunk sequence out of order",
                True,
            )
            return

        try:
            chunk = base64.b64decode(data.encode("ascii"), validate=True)
        except Exception:
            await self.send_error(
                websocket,
                "pkg.upload.chunk",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "invalid base64 chunk",
                False,
            )
            return

        max_chunk = int(self.policy.get("maxChunkBytes", 262144))
        if len(chunk) > max_chunk:
            await self.send_error(
                websocket,
                "pkg.upload.chunk",
                request_id,
                role,
                "PKG_POLICY_LIMIT_EXCEEDED",
                "chunk exceeds maxChunkBytes",
                True,
            )
            return

        digest = hashlib.sha256(chunk).hexdigest()
        if isinstance(chunk_sha, str) and chunk_sha and digest != chunk_sha:
            await self.send_error(
                websocket,
                "pkg.upload.chunk",
                request_id,
                role,
                "PKG_UPLOAD_CHUNK_HASH_MISMATCH",
                "chunk sha256 mismatch",
                True,
            )
            return

        await self._append_to_file(session.path, chunk)

        session.expected_seq += 1
        session.bytes_received += len(chunk)

        await self.send_message(
            websocket,
            "ack",
            "pkg.upload.chunk",
            request_id,
            role,
            {
                "uploadId": upload_id,
                "state": "running",
                "bytesReceived": session.bytes_received,
            },
        )

    async def _install_uploaded_artifact(
        self,
        session: UploadSession,
    ) -> Tuple[int, str, str]:
        if session.manager == "opkg":
            return await self._run_command(["opkg", "install", session.path])
        if session.manager == "ros":
            workspace_root = str(self.policy.get("rosWorkspaceRoot", "/home/root/spiny_ws")).strip()
            external_lib_dir = str(self.policy.get("externalLibDir", "/opt/spiny/external/lib")).strip()
            ok_ros, message_ros, details_ros = await self._install_ros_archive_bundle(
                archive_path=session.path,
                workspace_root=workspace_root,
                external_lib_dir=external_lib_dir,
            )
            if not ok_ros:
                return 1, "", message_ros
            return 0, json.dumps(details_ros, ensure_ascii=True), ""
        cmd = ["pip3", "install", "--no-input"]
        if self._pip_binary_only():
            cmd += ["--only-binary", ":all:", "--prefer-binary"]
        cmd.append(session.path)
        return await self._run_command(cmd)

    async def _handle_upload_commit(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        upload_id = payload.get("uploadId")
        sha256_value = payload.get("sha256")
        install_now = bool(payload.get("installNow", False))

        if not isinstance(upload_id, str) or not isinstance(sha256_value, str):
            await self.send_error(
                websocket,
                "pkg.upload.commit",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "invalid upload.commit payload",
                False,
            )
            return

        session = self.uploads.get(upload_id)
        if not session:
            await self.send_error(
                websocket,
                "pkg.upload.commit",
                request_id,
                role,
                "PKG_UPLOAD_NOT_FOUND",
                "upload session not found",
                False,
            )
            return

        if session.bytes_received != session.size_bytes:
            await self.send_error(
                websocket,
                "pkg.upload.commit",
                request_id,
                role,
                "PKG_POLICY_LIMIT_EXCEEDED",
                "uploaded size mismatch",
                True,
            )
            return

        digest = await self._compute_file_sha256(session.path)

        if digest != sha256_value or digest != session.sha256:
            await self.send_error(
                websocket,
                "pkg.upload.commit",
                request_id,
                role,
                "PKG_UPLOAD_COMMIT_HASH_MISMATCH",
                "artifact sha256 mismatch",
                False,
            )
            return

        await self.send_message(
            websocket,
            "progress",
            "pkg.upload.commit",
            request_id,
            role,
            {
                "phase": "verify",
                "percent": 60,
                "message": "artifact verified",
                "uploadId": upload_id,
            },
        )

        if install_now and session.target == "install":
            rc, out, err = await self._install_uploaded_artifact(session)
            if rc != 0:
                await self.send_error(
                    websocket,
                    "pkg.upload.commit",
                    request_id,
                    role,
                    "PKG_INSTALL_DEPENDENCY_FAILED",
                    err or "artifact installation failed",
                    False,
                    details={"stdout": out, "stderr": err, "uploadId": upload_id},
                )
                return

        await self.send_message(
            websocket,
            "event",
            "pkg.upload.commit",
            request_id,
            role,
            {
                "result": "success",
                "uploadId": upload_id,
                "storedPath": session.path,
                "installed": bool(install_now and session.target == "install"),
                "warnings": [],
            },
        )

    async def _handle_upload_abort(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        upload_id = payload.get("uploadId")
        if not isinstance(upload_id, str):
            await self.send_error(
                websocket,
                "pkg.upload.abort",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "uploadId is required",
                False,
            )
            return

        session = self.uploads.pop(upload_id, None)
        if not session:
            await self.send_error(
                websocket,
                "pkg.upload.abort",
                request_id,
                role,
                "PKG_UPLOAD_NOT_FOUND",
                "upload session not found",
                False,
            )
            return

        try:
            os.remove(session.path)
        except FileNotFoundError:
            pass

        await self.send_message(
            websocket,
            "event",
            "pkg.upload.abort",
            request_id,
            role,
            {"result": "success", "uploadId": upload_id, "aborted": True},
        )

    async def _handle_node_list(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        del payload
        await self._reap_finished_nodes()
        nodes = [self._node_snapshot(node_id) for node_id in sorted(self.managed_nodes.keys())]
        await self.send_message(
            websocket,
            "event",
            "node.list",
            request_id,
            role,
            {"result": "success", "nodes": nodes},
        )

    async def _handle_node_status(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        await self._reap_finished_nodes()
        node_id = payload.get("nodeId")

        if node_id is None:
            nodes = [self._node_snapshot(item) for item in sorted(self.managed_nodes.keys())]
            await self.send_message(
                websocket,
                "event",
                "node.status",
                request_id,
                role,
                {"result": "success", "nodes": nodes},
            )
            return

        if not isinstance(node_id, str):
            await self.send_error(
                websocket,
                "node.status",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "nodeId must be string",
                False,
            )
            return

        if node_id not in self.managed_nodes:
            await self.send_error(
                websocket,
                "node.status",
                request_id,
                role,
                "NODE_NOT_FOUND",
                "node not found in manifest",
                False,
            )
            return

        await self.send_message(
            websocket,
            "event",
            "node.status",
            request_id,
            role,
            {"result": "success", "node": self._node_snapshot(node_id)},
        )

    async def _handle_node_start(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        node_id = payload.get("nodeId")
        if not isinstance(node_id, str):
            await self.send_error(
                websocket,
                "node.start",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "nodeId must be string",
                False,
            )
            return

        if node_id not in self.managed_nodes:
            await self.send_error(
                websocket,
                "node.start",
                request_id,
                role,
                "NODE_NOT_FOUND",
                "node not found in manifest",
                False,
            )
            return

        runtime = self.node_runtimes.get(node_id)
        if runtime and runtime.process.returncode is None:
            await self.send_error(
                websocket,
                "node.start",
                request_id,
                role,
                "NODE_ALREADY_RUNNING",
                "node already running",
                False,
            )
            return

        await self.send_message(
            websocket,
            "ack",
            "node.start",
            request_id,
            role,
            {"state": "accepted", "nodeId": node_id},
        )

        ok, info = await self._start_managed_node(node_id)
        if not ok:
            await self.send_error(
                websocket,
                "node.start",
                request_id,
                role,
                "NODE_START_FAILED",
                info,
                False,
            )
            return

        await self.send_message(
            websocket,
            "event",
            "node.start",
            request_id,
            role,
            {"result": "success", "node": self._node_snapshot(node_id)},
        )

    async def _handle_node_stop(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        node_id = payload.get("nodeId")
        grace = payload.get("graceSec", 5)

        if not isinstance(node_id, str):
            await self.send_error(
                websocket,
                "node.stop",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "nodeId must be string",
                False,
            )
            return
        if not isinstance(grace, int):
            grace = 5

        if node_id not in self.managed_nodes:
            await self.send_error(
                websocket,
                "node.stop",
                request_id,
                role,
                "NODE_NOT_FOUND",
                "node not found in manifest",
                False,
            )
            return

        ok, info = await self._stop_managed_node(node_id, grace_sec=grace)
        if not ok:
            await self.send_error(
                websocket,
                "node.stop",
                request_id,
                role,
                "NODE_STOP_FAILED",
                info,
                False,
            )
            return

        await self.send_message(
            websocket,
            "event",
            "node.stop",
            request_id,
            role,
            {"result": "success", "nodeId": node_id, "state": "stopped"},
        )

    async def _handle_node_restart(
        self,
        websocket: websockets.WebSocketServerProtocol,
        request_id: str,
        role: str,
        payload: Dict[str, Any],
    ) -> None:
        node_id = payload.get("nodeId")
        if not isinstance(node_id, str):
            await self.send_error(
                websocket,
                "node.restart",
                request_id,
                role,
                "WS_SCHEMA_INVALID",
                "nodeId must be string",
                False,
            )
            return

        if node_id not in self.managed_nodes:
            await self.send_error(
                websocket,
                "node.restart",
                request_id,
                role,
                "NODE_NOT_FOUND",
                "node not found in manifest",
                False,
            )
            return

        runtime = self.node_runtimes.get(node_id)
        if runtime and runtime.process.returncode is None:
            ok_stop, info_stop = await self._stop_managed_node(node_id, grace_sec=5)
            if not ok_stop:
                await self.send_error(
                    websocket,
                    "node.restart",
                    request_id,
                    role,
                    "NODE_STOP_FAILED",
                    info_stop,
                    False,
                )
                return

        ok_start, info_start = await self._start_managed_node(node_id)
        if not ok_start:
            await self.send_error(
                websocket,
                "node.restart",
                request_id,
                role,
                "NODE_START_FAILED",
                info_start,
                False,
            )
            return

        await self.send_message(
            websocket,
            "event",
            "node.restart",
            request_id,
            role,
            {"result": "success", "node": self._node_snapshot(node_id)},
        )

    async def _handle_command(
        self,
        websocket: websockets.WebSocketServerProtocol,
        role: str,
        body: Dict[str, Any],
    ) -> None:
        action = body["action"]
        request_id = body["requestId"]
        payload = body["payload"]

        if not self._check_permission(role, action):
            await self.send_error(
                websocket,
                action,
                request_id,
                role,
                "WS_AUTH_FORBIDDEN_ROLE",
                "role is not allowed for this action",
                False,
            )
            return

        if action == "pkg.list":
            await self._handle_pkg_list(websocket, request_id, role, payload)
        elif action == "pkg.missing":
            await self._handle_pkg_missing(websocket, request_id, role, payload)
        elif action == "user.info":
            await self._handle_user_info(websocket, request_id, role, payload)
        elif action == "pkg.status":
            await self._handle_pkg_status(websocket, request_id, role, payload)
        elif action == "pkg.install":
            await self._handle_pkg_install(websocket, request_id, role, payload)
        elif action == "pkg.upload.begin":
            await self._handle_upload_begin(websocket, request_id, role, payload)
        elif action == "pkg.upload.chunk":
            await self._handle_upload_chunk(websocket, request_id, role, payload)
        elif action == "pkg.upload.commit":
            await self._handle_upload_commit(websocket, request_id, role, payload)
        elif action == "pkg.upload.abort":
            await self._handle_upload_abort(websocket, request_id, role, payload)
        elif action == "node.list":
            await self._handle_node_list(websocket, request_id, role, payload)
        elif action == "node.status":
            await self._handle_node_status(websocket, request_id, role, payload)
        elif action == "node.start":
            await self._handle_node_start(websocket, request_id, role, payload)
        elif action == "node.stop":
            await self._handle_node_stop(websocket, request_id, role, payload)
        elif action == "node.restart":
            await self._handle_node_restart(websocket, request_id, role, payload)
        elif action == "graph.snapshot":
            await self._handle_graph_snapshot(websocket, request_id, role, payload)
        elif action == "node.io.inspect":
            await self._handle_node_io_inspect(websocket, request_id, role, payload)
        elif action == "orchestrator.reload":
            await self._handle_orchestrator_reload(websocket, request_id, role, payload)
        elif action == "capture.window":
            await self._handle_capture_window(websocket, request_id, role, payload)
        elif action == "stream.subscribe":
            await self._handle_stream_subscribe(websocket, request_id, role, payload)
        elif action == "stream.unsubscribe":
            await self._handle_stream_unsubscribe(websocket, request_id, role, payload)
        elif action == "peer.list":
            await self._handle_peer_list(websocket, request_id, role, payload)
        elif action in {"peer.node.status", "peer.node.start", "peer.node.stop", "peer.node.restart"}:
            await self._handle_peer_node_action(websocket, request_id, role, action, payload)

    async def handle_connection(
        self,
        websocket: websockets.WebSocketServerProtocol,
        path: str,
    ) -> None:
        token = parse_token(path, websocket.request_headers)
        role = self.role_for_token(token)

        if not role:
            await self.send_error(
                websocket,
                "connect",
                None,
                None,
                "WS_AUTH_INVALID_TOKEN",
                "missing or invalid token",
                False,
            )
            await websocket.close(code=1008, reason="unauthorized")
            return

        self.logger.info("client connected role=%s path=%s", role, path)

        await self.send_message(
            websocket,
            "event",
            "connect",
            None,
            role,
            {
                "result": "success",
                "role": role,
                "permissions": sorted(list(ROLE_PERMISSIONS.get(role, set()))),
                "deviceId": self.device_id,
            },
        )

        try:
            async for raw in websocket:
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    await self.send_error(
                        websocket,
                        "unknown",
                        None,
                        role,
                        "WS_SCHEMA_INVALID",
                        "invalid json",
                        False,
                    )
                    continue

                if not isinstance(body, dict):
                    await self.send_error(
                        websocket,
                        "unknown",
                        None,
                        role,
                        "WS_SCHEMA_INVALID",
                        "message must be object",
                        False,
                    )
                    continue

                err = self._validate_envelope(body)
                if err:
                    await self.send_error(
                        websocket,
                        str(body.get("action", "unknown")),
                        body.get("requestId"),
                        role,
                        "WS_SCHEMA_INVALID",
                        err,
                        False,
                    )
                    continue

                await self._handle_command(websocket, role, body)
        finally:
            self._cleanup_connection_subscriptions(websocket)

    async def _reconcile_nodes(self) -> None:
        self.logger.info("reconciling node states with manifest")
        
        # 1. Stop nodes that are no longer in the manifest
        nodes_to_stop = []
        for node_id in list(self.node_runtimes.keys()):
            if node_id not in self.managed_nodes:
                nodes_to_stop.append(node_id)
        
        for node_id in nodes_to_stop:
            self.logger.info("stopping node %s (removed from manifest)", node_id)
            await self._stop_managed_node(node_id)

        # 2. Start nodes that are in the manifest but not running
        for node_id in self.managed_nodes:
            runtime = self.node_runtimes.get(node_id)
            is_running = runtime and runtime.process and runtime.process.returncode is None
            
            if not is_running:
                self.logger.info("starting node %s (from manifest)", node_id)
                ok, err = await self._start_managed_node(node_id)
                if not ok:
                    self.logger.error("failed to start node %s: %s", node_id, err)

    async def run(self) -> None:
        self.logger.info(
            "starting orchestrator host=%s port=%d device_id=%s",
            self.host,
            self.port,
            self.device_id,
        )

        # Initial reconciliation on startup
        reconcile_task = asyncio.create_task(self._reconcile_nodes())
        cleanup_task = asyncio.create_task(self._cleanup_stale_uploads())

        try:
            async with websockets.serve(
                self.handle_connection,
                self.host,
                self.port,
                max_size=None,
                ping_interval=20,
                ping_timeout=20,
            ):
                await asyncio.Future()
        finally:
            self.logger.info("stopping all running nodes before exit...")
            # attempt graceful stop for managed nodes; fall back to terminate
            for node_id in list(self.node_runtimes.keys()):
                try:
                    await self._stop_managed_node(node_id, grace_sec=2)
                except Exception:
                    runtime = self.node_runtimes.get(node_id)
                    if runtime and getattr(runtime, "process", None):
                        try:
                            runtime.process.terminate()
                        except Exception:
                            pass

            # cancel background tasks
            for t in (reconcile_task, cleanup_task):
                try:
                    t.cancel()
                except Exception:
                    pass


def main() -> None:
    service = SpinyOrchestrator()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
