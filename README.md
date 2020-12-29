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
ansible-playbook -i hosts playbooks/commun.yml
```

### Proxmox

When you create a new VM with Proxmox (assuming you know its IP):
1. Add a line in the inventory file (`hosts`)
2. Provide the `ansible_user` and `ansible_ssh_pass` of the first user
3. Provide the root password with `ansible_become_password`
4. Run the Proxmox provisioning playbook:
```shell
ansible-playbook -i hosts playbooks/proxmox_provisioner.yml -l <host>
```

Then, remove the extra variables (`ansible_user`, `ansible_ssh_pass` and 
`ansible_become_password`).

Finally, configure your `~/.ssh/config` in order to connect to the VM with your SSH key.

### Linux containers

You can also test the Neutrinet playbooks by provisioning linux containers (LXC) on your machine:
```shell
ansible-playbook -i hosts.lxd playbooks/lxd_provisioner.yml
```

By default, provisioned containers will be under Debian buster, but you can define another Debian release with the `debian_release` variable.

It is possible to configure LXD to provide domain name resolution for your containers.
1. First, check if the LXD DNS resolver is already configured:
```shell
# Assuming that the web container is up and running…
ping -c1 web.lxd
```
2. If the above command fails, then you need to configure a DNS resolver.  
   Retrieve the gateway's IPv4 from LXD's default network:
```shell
lxc network info lxdbr0 | grep inet
```
3. Copy the IPv4 line (starting with `inet`)
4. Add a new dnsmasq config file with the following content (replace <ip> with the gateway's IPv4):
```
bind-interfaces
except-interface=lxdbr0
server=/lxd/<ip>
```

The last step will depend on your OS.[^1] Usually, it will be located in `/etc/dnsmasq.d/`. Note that NetworkManager includes its own dnsmasq service, which means you will need to add the file in `/etc/NetworkManager/dnsmasq.d/`. Don't forget to reload dnsmasq (or NetworkManager) for the changes to take effect. If you experience some network issues with NetworkManager, try to restart your computer, it sometimes works...

Once the DNS resolver is configured, you might want to configure your `~/.ssh/config` with something like:
```
Host *.lxd
  PreferredAuthentications publickey
  User <username>
  IdentityFile <path/to/your/neutrinet/ssh/privatekey>
```

After that, you will be able to easily connect to one of the containers with your public key. For instance:
```shell
ssh web.lxd
```

# References

[^1]: https://discuss.linuxcontainers.org/t/dns-for-lxc-containers/235/4