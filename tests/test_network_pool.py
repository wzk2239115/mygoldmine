import ipaddress
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/redteam"))
from network_pool import select_subnet


def test_small_subnets_avoid_host_routes_and_existing_labs():
    networks = [{"IPAM": {"Config": [{"Subnet": "10.224.0.0/28"}]}}]
    routes = [{"dst": "default"}, {"dst": "10.225.0.0/16"}]
    result = ipaddress.ip_network(select_subnet(networks, routes))
    assert result.prefixlen == 28
    assert not result.overlaps(ipaddress.ip_network("10.224.0.0/28"))
    assert not result.overlaps(ipaddress.ip_network("10.225.0.0/16"))


def test_one_hundred_fifty_labs_fit_without_default_pool():
    networks = []
    for _ in range(150):
        subnet = select_subnet(networks, [])
        assert subnet not in [row["IPAM"]["Config"][0]["Subnet"] for row in networks]
        networks.append({"IPAM": {"Config": [{"Subnet": subnet}]}})
