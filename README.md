# Ansible playbooks for Neutrinet

## Installation

Install Ansible and its dependencies in a python3 virtual env:
```shell
virtualenv env
env/bin/pip install -r requirements.txt
source env/bin/activate
```

## Pre-commit
We use pre-commit to validate merge requests.
It is strongly advised to add pre-commit on your computer to avoid your merge request to be refused.

You can run this command in your virtualenv.
```bash
pre-commit install
```

## Git-secret

We use [git-secret](https://git-secret.io) to protect sensitive data such as the key to encrypt / decrypt Ansible vaults.

In order to decrypt these secrets, you must [install git-secret on your computer](https://git-secret.io/installation). You must also have a GPG key pair to be able to decrypt the secrets.

This git repository has been configured for git-secret as follows:
```bash
git-secret init
git secret tell <email address>
git secret add vault.key
git secret hide
```
These steps must be done **once**.

### Add a new user

Add the GPG key of the user:
```bash
git secret tell <email address>
```
or
```bash
git --homedir .gitsecret/keys --import <pubkey file>
```

Then, reencrypt the secrets:
```bash
git secret hide
```

Don't forget to commit and push your changes!

### Decrypt the secrets

After cloning the repository, just run:
```bash
git secret reveal
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
