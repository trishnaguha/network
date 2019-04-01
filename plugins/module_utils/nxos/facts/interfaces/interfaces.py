#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2019 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The nxos interfaces fact class
It is in this file the configuration is collected from the device
for a given resource, parsed, and the facts tree is populated
based on the configuration.
"""
import re
from copy import deepcopy
from ansible_collections.ansible_network.network.plugins.module_utils. \
     nxos.facts.base import FactsBase
from ansible_collections.ansible_network.network.plugins.module_utils. \
     nxos.utils.utils import get_interface_type, normalize_interface


class InterfacesFacts(FactsBase):
    """ The nxos interfaces fact class
    """

    def populate_facts(self, module, connection, data=None):
        """ Populate the facts for interfaces

        :param module: the module instance
        :param connection: the device connection
        :param data: previously collected conf
        :rtype: dictionary
        :returns: facts
        """
        objs = []

        if not data:
           data = connection.get('show running-config | section ^interface')

        # operate on a collection of resource x
        config = data.split('interface ')
        for conf in config:
            if conf:
                obj = self.render_config(self.generated_spec, conf)
                if obj:
                    objs.append(obj)
        facts = {}
        if objs:
            facts['interfaces'] = objs
        self.ansible_facts['net_configuration'].update(facts)
        return self.ansible_facts

    def render_config(self, spec, conf):
        """
        Render config as dictionary structure and delete keys from spec for null values

        :param spec: The facts tree, generated from the argspec
        :param conf: The configuration
        :rtype: dictionary
        :returns: The generated config
        """
        config = deepcopy(spec)

        # populate the facts from the configuration
        match = re.search(r'^(\S+)', conf)
        intf = match.group(1)
        if get_interface_type(intf) == 'unknown':
            return {}
        config['name'] = normalize_interface(intf)

        config['description'] = self.parse_conf_arg(conf, 'description')
        config['speed'] = self.parse_conf_arg(conf, 'speed')
        config['mtu'] = self.parse_conf_arg(conf, 'mtu')
        config['duplex'] = self.parse_conf_arg(conf, 'duplex')
        config['mode'] = self.parse_conf_cmd_arg(conf, 'switchport', 'layer2', res2='layer3')
        enable = self.parse_conf_cmd_arg(conf, 'shutdown', False)
        config['enable'] = enable if enable is not None else config['enable']
        config['fabric_forwarding_anycast_gateway'] = self.parse_conf_cmd_arg(conf, 'fabric forwarding mode anycast-gateway', True, res2=False)
        config['ip_forward'] = self.parse_conf_cmd_arg(conf, 'ip forward', 'enable', res2='disable')

        return self.generate_final_config(config)
