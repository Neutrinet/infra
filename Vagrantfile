# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.define "web.neutri.net" do |config|
    config.vm.box = "debian/stretch64"
    config.vm.hostname = "web.neutri.net"
    config.vm.network "private_network", ip: "192.168.33.10"
  end
end
