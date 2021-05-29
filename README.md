# Ansible playbooks for Neutrinet

## Installation

Install Ansible and its dependencies in a python3 virtual env:
```shell
virtualenv env
env/bin/pip install -r requirements.txt
source env/bin/activate
```

## Pre-comit
We use pre-commit to validate merge requests.
It is strongly advised to add pre-commit on your computer to avoid your merge request to be refused.

You can run this command in your virtualenv.
```
pre-commit install
```

## Usage

### Production

Run the following to setup the common config for all hosts:
```shell
ansible-playbook playbooks/production.yml
```

## Adding VM cluster patata

### Preamble
The first step is to choose a free ip and enter it in pfsense.

We prefer ipv6.

### Complete the IPAM
You have to go to [this page](https://wiki.neutrinet.be/fr/infra/network/ipam#neutrinet_patata) and complete it

### pfsense
You have to go to the [pfsense master](https://[2001:913:1000:10::61]/).

Then go to Services -> DNS Resolver
At the bottom of the page you can add a dns entry.

### Proxmox
https://wiki.neutrinet.be/fr/infra/notes_sur_infra_de_neutrinet#creation_d_une_machine_virtuelle_avec_proxmox
There is an iso "preseed-debian-10-root-neutrinet.iso" that does a minimal self-installation of debian with only the root user and his password is "neutrinet"

### First launch of ansible
Once you have filled in your vm in the inventories/production.ini file you can run this command for the first provision of the vm.
```
ansible-playbook -l <the name of your vm> -k -u root playbooks/production.yml
```
You will be asked for a password and the answer is "neutrinet".

The playbook will stop after the restart of ssh. This is normal from now on you don't have to specify `-l <the name of your vm> -k -u root` on the command line.

### Molecule
