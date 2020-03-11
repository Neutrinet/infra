# Ansible playbooks for Neutrinet

## Installation

Install Ansible and its dependencies in a python3 virtual env:
```shell
virtualenv env
env/bin/pip install -r requirements.txt
source env/bin/activate
```

If you are planning to use linux containers (LXC), you will need to install the following package:
```shell
sudo apt install lxd
sudo systemctl start lxd
```

You should add your user to the `lxd` group if you want to run LXC commands without being root:
```shell
usermod -G lxd -a <user>
```
This will be effective at your next login session.

## Usage

Run the following to setup the common config for all hosts:
```shell
ansible-playbook -i hosts playbooks-infra/commun.yml
```

You can also test the Neutrinet playbooks by provisioning linux containers (LXC) on your machine:
```shell
ansible-playbook -i hosts.local provisioners/lxd.yml
```

By default, provisioned containers will be under Debian buster, but you can define another Debian release with the `debian_release` variable.
