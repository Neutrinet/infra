#!/usr/bin/env python3

import vagrant
import json


def get_running_vms():
    v = vagrant.Vagrant()
    vms = v.status()  # Returns a list of tuples (vm_name, state)

    running_vms = [vm.name for vm in vms if vm.state == "running"]
    return running_vms


def generate_inventory(vms):
    """
    Generates an Ansible inventory from a list of running VMs.
    """
    inventory = {
        "all": {"hosts": []},
        "vagrant": {"hosts": []},
        "backup": {"hosts": []},
        "_meta": {"hostvars": {}},
    }
    if "backup-storage.vagrant.neutri.net" in vms:
        inventory["all"]["hosts"].append("backup-storage.vagrant.neutri.net")
        inventory["vagrant"]["hosts"].append("backup-storage.vagrant.neutri.net")
        inventory["backup"]["hosts"].append("backup-storage.vagrant.neutri.net")

    return inventory


if __name__ == "__main__":
    vms = get_running_vms()
    inventory = generate_inventory(vms)

    # Ansible attend que le script produise une sortie JSON
    print(json.dumps(inventory))
