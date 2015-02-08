#! /usr/bin/python
import sys
import os
import time
import fcntl
import struct
import socket
import subprocess
from common import *

# These are module names which are not installed by default.
# These modules will be loaded later after downloading
iniparse = None
psutil = None

# =============================================================================
# ==================   Components Installation Starts Here ====================
# =============================================================================

my_ip = get_ip_address('eth1')
ip_address = raw_input('Controller IP: ')
ip_address_mgnt = raw_input('Controller Mgmt IP: ')


def install_and_configure_ntp():
    execute("apt-get install ntp -y")
    execute("sed -i 's/server 0.ubuntu.pool.ntp.org/#server 0.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server 1.ubuntu.pool.ntp.org/#server 1.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server 2.ubuntu.pool.ntp.org/#server 2.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server 3.ubuntu.pool.ntp.org/#server 3.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server ntp.ubuntu.com/server %s/g' /etc/ntp.conf" % ip_address)
    execute("service ntp restart", True)


def install_and_configure_nova():
    nova_conf = "/etc/nova/nova.conf"
    nova_paste_conf = "/etc/nova/api-paste.ini"
    nova_compute_conf = "/etc/nova/nova-compute.conf"

    execute("apt-get install qemu-kvm libvirt-bin python-libvirt -y")
    execute("apt-get install nova-compute-kvm novnc -y", True)

    add_to_conf(nova_paste_conf, "filter:authtoken", "auth_host", ip_address_mgnt)
    add_to_conf(nova_paste_conf, "filter:authtoken", "auth_port", "35357")
    add_to_conf(nova_paste_conf, "filter:authtoken", "auth_protocol", "http")
    add_to_conf(nova_paste_conf, "filter:authtoken", "admin_tenant_name", "service")
    add_to_conf(nova_paste_conf, "filter:authtoken", "admin_user", "nova")
    add_to_conf(nova_paste_conf, "filter:authtoken", "admin_password", "nova")

    add_to_conf(nova_conf, "DEFAULT", "logdir", "/var/log/nova")
    add_to_conf(nova_conf, "DEFAULT", "verbose", "True")
    add_to_conf(nova_conf, "DEFAULT", "debug", "True")
    add_to_conf(nova_conf, "DEFAULT", "lock_path", "/var/lib/nova")
    add_to_conf(nova_conf, "DEFAULT", "rabbit_host", ip_address_mgnt)
    add_to_conf(nova_conf, "DEFAULT", "sql_connection", "mysql://nova:nova@%s/nova" % ip_address_mgnt)
    add_to_conf(nova_conf, "DEFAULT", "glance_api_servers", "%s:9292" % ip_address_mgnt)
    add_to_conf(nova_conf, "DEFAULT", "compute_driver", "libvirt.LibvirtDriver")
    add_to_conf(nova_conf, "DEFAULT", "dhcpbridge_flagfile", "/etc/nova/nova.conf")
    add_to_conf(nova_conf, "DEFAULT", "firewall_driver", "nova.virt.firewall.NoopFirewallDriver")
    add_to_conf(nova_conf, "DEFAULT", "security_group_api", "neutron")
    add_to_conf(nova_conf, "DEFAULT", "libvirt_vif_driver", "nova.virt.libvirt.vif.LibvirtGenericVIFDriver")
    add_to_conf(nova_conf, "DEFAULT", "root_helper", "sudo nova-rootwrap /etc/nova/rootwrap.conf")
    add_to_conf(nova_conf, "DEFAULT", "compute_driver", "libvirt.LibvirtDriver")
    add_to_conf(nova_conf, "DEFAULT", "auth_strategy", "keystone")
    add_to_conf(nova_conf, "DEFAULT", "novnc_enabled", "true")
    add_to_conf(nova_conf, "DEFAULT", "novncproxy_base_url", "http://%s:6080/vnc_auto.html" % ip_address)
    add_to_conf(nova_conf, "DEFAULT", "novncproxy_port", "6080")
    add_to_conf(nova_conf, "DEFAULT", "vncserver_proxyclient_address", my_ip)
    add_to_conf(nova_conf, "DEFAULT", "vncserver_listen", "0.0.0.0")
    add_to_conf(nova_conf, "DEFAULT", "network_api_class", "nova.network.neutronv2.api.API")
    add_to_conf(nova_conf, "DEFAULT", "neutron_admin_username", "neutron")
    add_to_conf(nova_conf, "DEFAULT", "neutron_admin_password", "neutron")
    add_to_conf(nova_conf, "DEFAULT", "neutron_admin_tenant_name", "service")
    add_to_conf(nova_conf, "DEFAULT", "neutron_admin_auth_url", "http://%s:5000/v2.0/" % ip_address_mgnt)
    add_to_conf(nova_conf, "DEFAULT", "neutron_auth_strategy", "keystone")
    add_to_conf(nova_conf, "DEFAULT", "neutron_url", "http://%s:9696/" % ip_address_mgnt)
    add_to_conf(nova_conf, "DEFAULT", "metadata_host", "%s" % ip_address_mgnt)
    add_to_conf(nova_conf, "DEFAULT", "service_neutron_metadata_proxy", "True")
    add_to_conf(nova_conf, "DEFAULT", "neutron_metadata_proxy_shared_secret", "helloOpenStack")

    add_to_conf(nova_compute_conf, "DEFAULT", "libvirt_type", "qemu")
    add_to_conf(nova_compute_conf, "DEFAULT", "compute_driver", "libvirt.LibvirtDriver")
    add_to_conf(nova_compute_conf, "DEFAULT", "libvirt_vif_type", "ethernet")

    execute("service libvirt-bin restart", True)
    execute("service nova-compute restart", True)


def install_and_configure_ovs():
    neutron_conf = "/etc/neutron/neutron.conf"
    neutron_paste_conf = "/etc/neutron/api-paste.ini"
    neutron_plugin_conf = "/etc/neutron/plugins/ml2/ml2_conf.ini"
    execute("apt-get install openvswitch-switch openvswitch-datapath-dkms -y", True)

    execute("ovs-vsctl --may-exist add-br br-int")

    execute("apt-get install neutron-plugin-ml2 neutron-plugin-openvswitch-agent -y", True)

    add_to_conf(neutron_conf, "DEFAULT", "core_plugin", "neutron.plugins.openvswitch.ovs_neutron_plugin.OVSNeutronPluginV2")
    add_to_conf(neutron_conf, "DEFAULT", "verbose", "True")
    add_to_conf(neutron_conf, "DEFAULT", "debug", "True")
    add_to_conf(neutron_conf, "DEFAULT", "auth_strategy", "keystone")
    add_to_conf(neutron_conf, "DEFAULT", "rabbit_host", ip_address_mgnt)
    add_to_conf(neutron_conf, "DEFAULT", "rabbit_port", "5672")
    add_to_conf(neutron_conf, "DEFAULT", "allow_overlapping_ips", "False")
    add_to_conf(neutron_conf, "DEFAULT", "root_helper", "sudo neutron-rootwrap /etc/neutron/rootwrap.conf")

    add_to_conf(neutron_paste_conf, "filter:authtoken", "auth_host", ip_address_mgnt)
    add_to_conf(neutron_paste_conf, "filter:authtoken", "auth_port", "35357")
    add_to_conf(neutron_paste_conf, "filter:authtoken", "auth_protocol", "http")
    add_to_conf(neutron_paste_conf, "filter:authtoken", "admin_tenant_name", "service")
    add_to_conf(neutron_paste_conf, "filter:authtoken", "admin_user", "neutron")
    add_to_conf(neutron_paste_conf, "filter:authtoken", "admin_password", "neutron")

    add_to_conf(neutron_plugin_conf, "DATABASE", "sql_connection", "mysql://neutron:neutron@%s/neutron" % ip_address_mgnt)
    add_to_conf(neutron_plugin_conf, "OVS", "enable_tunneling", "True")
    add_to_conf(neutron_plugin_conf, "OVS", "local_ip", my_ip)
    add_to_conf(neutron_plugin_conf, "OVS", "tunnel_type", "gre")
    add_to_conf(neutron_plugin_conf, "OVS", "integration_bridge", "br-int")
    add_to_conf(neutron_plugin_conf, "securitygroup", "firewall_driver", "neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver")
    add_to_conf(neutron_plugin_conf, "securitygroup", "enable_security_group", "True")

    execute("service neutron-plugin-openvswitch-agent restart", True)
    execute("service openvswitch-switch restart", True)

initialize_system()
install_and_configure_ntp()
install_and_configure_nova()
install_and_configure_ovs()
