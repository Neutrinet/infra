#!/usr/bin/python3
"""Subscribe the X710 PF bond to the solicited-node group of every address carried by a VF.

The X710 hands a multicast frame matching a VF filter to that VF only. When a bridged address
(host or virtio VM) shares its solicited-node group with an address on a VF, neighbor discovery
to it never reaches the PF. Subscribing the bond to every VF group covers any bridged address.
"""

import ipaddress
import subprocess
import sys
from pathlib import Path

ADDRESSES_FILE = Path("/etc/neutrinet/pf-mcast-addresses")
BOND_DEVICE = "bond0"
SOLICITED_NODE_PREFIX = "33:33:ff:"


def solicited_node_group(address: str) -> str:
	low_24_bits = int(ipaddress.IPv6Address(address)) & 0xFFFFFF
	group_bytes = low_24_bits.to_bytes(3, "big")
	return SOLICITED_NODE_PREFIX + ":".join(f"{group_byte:02x}" for group_byte in group_bytes)


def read_addresses(addresses_text: str) -> list[str]:
	addresses = []
	for line in addresses_text.splitlines():
		address = line.split("#", 1)[0].strip()
		if address:
			addresses.append(address)
	return addresses


def static_solicited_node_groups(maddr_output: str) -> set[str]:
	groups = set()
	for line in maddr_output.splitlines():
		fields = line.split()
		is_static_link_group = len(fields) >= 2 and fields[0] == "link" and fields[-1] == "static"
		if is_static_link_group and fields[1].startswith(SOLICITED_NODE_PREFIX):
			groups.add(fields[1])
	return groups


def plan_changes(wanted_groups: set[str], current_groups: set[str]) -> tuple[list[str], list[str]]:
	groups_to_add = sorted(wanted_groups - current_groups)
	groups_to_remove = sorted(current_groups - wanted_groups)
	return groups_to_add, groups_to_remove


def run_ip(*arguments: str) -> str:
	return subprocess.run(["/usr/sbin/ip", *arguments], check=True, stdout=subprocess.PIPE, text=True).stdout


def main() -> int:
	wanted_groups = {solicited_node_group(address) for address in read_addresses(ADDRESSES_FILE.read_text(encoding="utf-8"))}
	current_groups = static_solicited_node_groups(run_ip("maddr", "show", "dev", BOND_DEVICE))
	groups_to_add, groups_to_remove = plan_changes(wanted_groups, current_groups)
	for group in groups_to_add:
		run_ip("maddr", "add", group, "dev", BOND_DEVICE)
		print(f"{group} added")
	for group in groups_to_remove:
		run_ip("maddr", "del", group, "dev", BOND_DEVICE)
		print(f"{group} removed")
	return 0


if __name__ == "__main__":
	sys.exit(main())
