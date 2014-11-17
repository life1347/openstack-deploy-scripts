#! /usr/bin/python
import sys
import os
import time
import fcntl
import struct
import socket
import subprocess
import common
from common import *

# These are module names which are not installed by default.
# These modules will be loaded later after downloading
iniparse = None
psutil = None

#=================================================================================
#==================   Components Installation Starts Here ========================
#=================================================================================

my_ip = get_ip_address('eth1')
ip_address = raw_input('Controller IP: ')
ip_address_mgnt = raw_input('Controller Mgmt IP: ')

def install_and_configure_ntp():
    execute("apt-get install ntp -y")
    execute("sed -i 's/server 0.ubuntu.pool.ntp.org/#server 0.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server 1.ubuntu.pool.ntp.org/#server 1.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server 2.ubuntu.pool.ntp.org/#server 2.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server 3.ubuntu.pool.ntp.org/#server 3.ubuntu.pool.ntp.org/g' /etc/ntp.conf")
    execute("sed -i 's/server ntp.ubuntu.com/server %s/g' /etc/ntp.conf" %ip_address)
    execute("service ntp restart", True)


def install_and_configure_neutron():
    neutron_conf = "/etc/neutron/neutron.conf"
    neutron_paste_conf = "/etc/neutron/api-paste.ini"
    neutron_plugin_conf = "/etc/neutron/plugins/ml2/ml2_conf.ini"
    neutron_dhcp_ini="/etc/neutron/dhcp_agent.ini"
    neutron_l3_ini="/etc/neutron/l3_agent.ini"
    neutron_metadata_ini="/etc/neutron/metadata_agent.ini"
    execute("apt-get install openvswitch-switch openvswitch-datapath-dkms -y", True)

    execute("ovs-vsctl --may-exist add-br br-int")
    execute("ovs-vsctl --may-exist add-br br-ex")
    execute("ovs-vsctl --may-exist add-port br-ex eth2")
    execute("apt-get install neutron-plugin-openvswitch-agent neutron-dhcp-agent neutron-l3-agent neutron-metadata-agent -y", True)

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

    add_to_conf(neutron_plugin_conf, "DATABASE", "sql_connection", "mysql://neutron:neutron@%s/neutron"%ip_address_mgnt)
    add_to_conf(neutron_plugin_conf, "OVS", "enable_tunneling", "True")
    add_to_conf(neutron_plugin_conf, "OVS", "local_ip", my_ip)
    add_to_conf(neutron_plugin_conf, "OVS", "tunnel_type", "gre")
    add_to_conf(neutron_plugin_conf, "OVS", "integration_bridge", "br-int")
    add_to_conf(neutron_plugin_conf, "securitygroup", "firewall_driver", "neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver")

    add_to_conf(neutron_dhcp_ini, "DEFAULT", "interface_driver", "neutron.agent.linux.interface.OVSInterfaceDriver")
    add_to_conf(neutron_dhcp_ini, "DEFAULT", "dhcp_driver", "neutron.agent.linux.dhcp.Dnsmasq")

    add_to_conf(neutron_l3_ini, "DEFAULT", "interface_driver", "neutron.agent.linux.interface.OVSInterfaceDriver")

    add_to_conf(neutron_metadata_ini, "DEFAULT", "auth_url", "http://%s:5000/v2.0"%ip_address_mgnt)
    add_to_conf(neutron_metadata_ini, "DEFAULT", "auth_region", "region")
    add_to_conf(neutron_metadata_ini, "DEFAULT", "admin_tenant_name", "service")
    add_to_conf(neutron_metadata_ini, "DEFAULT", "admin_user", "neutron")
    add_to_conf(neutron_metadata_ini, "DEFAULT", "admin_password", "neutron")
    add_to_conf(neutron_metadata_ini, "DEFAULT", "nova_metadata_ip", "%s" %ip_address_mgnt)
    add_to_conf(neutron_metadata_ini, "DEFAULT", "nova_metadata_port", "8775")
    add_to_conf(neutron_metadata_ini, "DEFAULT", "metadata_proxy_shared_secret", "helloOpenStack")

    # Depending on your network interface driver, you may need to disable
    # Generic Receive Offload (GRO) to achieve suitable throughtput between
    # your instances and external network.
    # https://ask.openstack.org/en/question/29147/ssh-to-a-vm-causes-kernel-panic-on-icehouse-neutron-host/
    execute("ethtool -K eth2 gro off")
    execute("ethtool -K eth2 gso off")

    execute("service neutron-plugin-openvswitch-agent restart", True)
    execute("service neutron-dhcp-agent restart", True)
    execute("service neutron-l3-agent restart", True)

initialize_system()
install_and_configure_ntp()
install_and_configure_neutron()
