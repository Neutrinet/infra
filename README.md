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

### Production

Run the following to setup the common config for all hosts:
```shell
ansible-playbook -i hosts playbooks-infra/commun.yml
```

### Linux containers

You can also test the Neutrinet playbooks by provisioning linux containers (LXC) on your machine:
```shell
ansible-playbook -i hosts.lxc provisioners/lxd.yml --ask-become-password
```

By default, provisioned containers will be under Debian buster, but you can define another Debian release with the `debian_release` variable.

Ansible will prompt for your sudo password in order to setup your `/etc/hosts`. You can run the playbook without `--ask-become-password` option, but then Ansible will probably fail to change your hosts file. Note that the playbook will ignore the error and continue its work.

Once the hosts file is configured, you might want to configure your `~/.ssh/config` with something like:
```
Host *.neutrinet.lxc
  PreferredAuthentications publickey
  User <username>
  IdentityFile <path/to/ssh/privatekey>
```

After that, you will be able to easily connect to one of the containers with your public key. For instance:
```shell
ssh web.neutrinet.lxc
```