"""Self-check of the PF multicast subscription helpers: python3 roles/proxmox/files/test_neutrinet_pf_mcast.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from neutrinet_pf_mcast import plan_changes, read_addresses, solicited_node_group, static_solicited_node_groups  # noqa: E402

MADDR_OUTPUT = """8:	bond0
	link  33:33:00:00:00:01 users 3
	link  33:33:ff:00:02:03 users 2 static
	link  33:33:ff:00:00:40 users 2 static
	link  33:33:ff:82:19:67 users 2
	inet6 ff02::1
"""

ADDRESSES_TEXT = """# edge-nlix bond0.13
2001:913:1000:101::1:203

2001:7f8:13::a520:4059:1  # edge-nlix bond0.53.7
fe80::a0ea:93ff:fed5:ff2b
"""


def test_solicited_node_group() -> None:
	assert solicited_node_group("2001:913:1000:101::1:203") == "33:33:ff:01:02:03"
	assert solicited_node_group("2001:7f8:13::a520:4059:1") == "33:33:ff:59:00:01"
	assert solicited_node_group("fe80::a0ea:93ff:fed5:ff2b") == "33:33:ff:d5:ff:2b"
	assert solicited_node_group("fe80:cafe::16") == "33:33:ff:00:00:16"


def test_read_addresses_skips_comments_and_blank_lines() -> None:
	assert read_addresses(ADDRESSES_TEXT) == ["2001:913:1000:101::1:203", "2001:7f8:13::a520:4059:1", "fe80::a0ea:93ff:fed5:ff2b"]


def test_static_groups_ignore_kernel_subscriptions() -> None:
	assert static_solicited_node_groups(MADDR_OUTPUT) == {"33:33:ff:00:02:03", "33:33:ff:00:00:40"}


def test_plan_changes_adds_missing_and_removes_stale() -> None:
	wanted_groups = {solicited_node_group(address) for address in read_addresses(ADDRESSES_TEXT)}
	groups_to_add, groups_to_remove = plan_changes(wanted_groups, static_solicited_node_groups(MADDR_OUTPUT))
	assert groups_to_add == ["33:33:ff:01:02:03", "33:33:ff:59:00:01", "33:33:ff:d5:ff:2b"]
	assert groups_to_remove == ["33:33:ff:00:00:40", "33:33:ff:00:02:03"]


if __name__ == "__main__":
	test_solicited_node_group()
	test_read_addresses_skips_comments_and_blank_lines()
	test_static_groups_ignore_kernel_subscriptions()
	test_plan_changes_adds_missing_and_removes_stale()
	print("ok")
