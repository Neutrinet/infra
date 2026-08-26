# Ansible playbooks for Neutrinet

## Installation

### 1. Clone the repository

```shell
git clone --recurse-submodules ssh://git@gitlab.domainepublic.net:3265/Neutrinet/infra-ansible.git
cd infra-ansible
```

If you already cloned without `--recurse-submodules`:
```shell
git submodule update --init --recursive
```

### 2. Install system dependencies

**Debian:**
```shell
sudo apt install python3 python3-venv direnv git-secret
```

**Fedora:**
```shell
sudo dnf install python3 direnv git-secret
```

**Manjaro:**
```shell
sudo pacman -S python direnv
yay -S git-secret
```

### 3. Set up direnv

direnv automatically activates the Python virtualenv whenever you enter the project directory.

```shell
cp .envrc.default .envrc
# Edit .envrc to match your setup (VAGRANT_DEFAULT_PROVIDER, PASSWORD_STORE_DIR…)
direnv allow
```

Then add direnv to your shell. Add the following to your `~/.bashrc` (or `~/.zshrc`):
```shell
eval "$(direnv hook bash)"
```

### 4. Install Python dependencies

```shell
pip install -r requirements.txt
```

direnv will have activated the `.venv/` virtualenv automatically.

### 5. Decrypt secrets

The repository uses [git-secret](https://git-secret.io) to protect sensitive files (Ansible vault key, etc.).

You need a GPG key that has been added to the repository by an existing member. Once that is done:

```shell
git secret reveal
```

See the [Git-secret](#git-secret) section below for more details.

### 6. Set up pre-commit hooks

```shell
pre-commit install
```

This validates your changes locally before each commit, avoiding rejected merge requests.

## Git-secret

We use [git-secret](https://git-secret.io) to protect sensitive data such as the Ansible vault key.

### Decrypt the secrets

After cloning the repository, run:
```bash
git secret reveal
```

### Add a new user

Get the new user's GPG public key and import it into your local keyring, then add them to the repository:

```bash
gpg --import <pubkey file>
git secret tell <email address>
```

Then re-encrypt the secrets with the new user's key:
```bash
git secret hide
```

Don't forget to commit and push your changes!

## Usage

### Production

Run the following to set up the common config for all hosts:
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

The playbook will stop after the restart of ssh. This is normal — from now on you don't have to specify `-l <the name of your vm> -k -u root` on the command line.

### Molecule
