"""Allocate small isolated subnets without changing Docker daemon defaults."""
import fcntl
import ipaddress
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def select_subnet(networks, routes):
    occupied = []
    for row in networks:
        for config in row.get("IPAM", {}).get("Config") or []:
            if config.get("Subnet"):
                occupied.append(ipaddress.ip_network(config["Subnet"], strict=False))
    for route in routes:
        if route.get("dst") and route["dst"] != "default":
            occupied.append(ipaddress.ip_network(route["dst"], strict=False))
    for pool in ("10.224.0.0/12", "172.16.0.0/12", "192.168.0.0/16"):
        for candidate in ipaddress.ip_network(pool).subnets(new_prefix=28):
            if not any(other.version == 4 and candidate.overlaps(other) for other in occupied):
                return str(candidate)
    raise ValueError("没有与 Docker 网络及宿主机路由隔离的可用实验子网")


def create_network(docker, name, project, run_id):
    lock = ROOT / ".runtime/locks/redteam-network-pool.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        ids = docker(["network", "ls", "-q"]).stdout.split()
        networks = json.loads(docker(["network", "inspect", *ids]).stdout) if ids else []
        route = subprocess.run(["ip", "-j", "-4", "route", "show", "table", "all"],
                               capture_output=True, text=True, check=True, timeout=10)
        subnet = select_subnet(networks, json.loads(route.stdout))
        docker(["network", "create", "--internal", "--subnet", subnet,
                "--label", "mygoldmine.owner=redteam",
                "--label", "mygoldmine.project=" + project,
                "--label", "mygoldmine.run=" + run_id, name])
        return subnet
