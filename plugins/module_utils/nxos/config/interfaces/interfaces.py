#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2019 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The nxos_interfaces class
It is in this file where the current configuration (as dict)
is compared to the provided configuration (as dict) and the command set
necessary to bring the current configuration to it's desired end-state is
created
"""

from ansible.module_utils.network.common.utils import to_list
from ansible.module_utils.six import iteritems

from ansible_collections.ansible_network.network.plugins.module_utils. \
     nxos.argspec.interfaces.interfaces import InterfacesArgs
from ansible_collections.ansible_network.network.plugins.module_utils. \
     nxos. \
     config.base import ConfigBase
from ansible_collections.ansible_network.network.plugins.module_utils. \
     nxos.facts.facts import Facts
from ansible_collections.ansible_network.network.plugins.module_utils. \
     nxos.utils.utils import get_interface_type, normalize_interface, \
     search_obj_in_list


class Interfaces(ConfigBase, InterfacesArgs):
    """
    The nxos_interfaces class
    """

    gather_subset = [
        'net_configuration_interfaces',
    ]

    def get_interfaces_facts(self):
        """ Get the 'facts' (the current configuration)

        :rtype: A dictionary
        :returns: The current configuration as a dictionary
        """
        facts = Facts().get_facts(self._module, self._connection, self.gather_subset)
        interfaces_facts = facts['net_configuration'].get('interfaces')
        if not interfaces_facts:
            return []
        return interfaces_facts

    def execute_module(self):
        """ Execute the module

        :rtype: A dictionary
        :returns: The result from moduel execution
        """
        result = {'changed': False}
        commands = list()
        warnings = list()

        commands.extend(self.set_config())
        if commands:
            if not self._module.check_mode:
                self._connection.edit_config(commands)
            result['changed'] = True
        result['commands'] = commands

        interfaces_facts = self.get_interfaces_facts()

        if not result['changed']:
            result['before'] = interfaces_facts
        if result['changed']:
            result['after'] = interfaces_facts

        result['warnings'] = warnings
        return result

    def set_config(self):
        """ Collect the configuration from the args passed to the module,
            collect the current configuration (as a dict from facts)

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the deisred configuration
        """
        want = self._module.params['config']
        for w in want:
             w.update({'name': normalize_interface(w['name'])})
        have = self.get_interfaces_facts()
        resp = self.set_state(want, have)
        return to_list(resp)

    def set_state(self, want, have):
        """ Select the appropriate function based on the state provided

        :param want: the desired configuration as a dictionary
        :param have: the current configuration as a dictionary
        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the deisred configuration
        """
        state = self._module.params['state']
        commands = []

        if state == 'overridden':
            commands.extend(self._state_overridden(want, have))
        else:
            for w in want:
                name = w['name']
                interface_type = get_interface_type(name)
                obj_in_have = search_obj_in_list(name, have)
                kwargs = {'w': w, 'obj_in_have': obj_in_have, 'interface_type': interface_type}

                if state == 'deleted':
                    commands.extend(self._state_deleted(**kwargs))

                if state == 'merged':
                    commands.extend(self._state_merged(**kwargs))

                if state == 'replaced':
                    commands.extend(self._state_replaced(**kwargs))

        return commands

    def _state_replaced(self, w, obj_in_have, interface_type):
        """ The command generator when state is replaced

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the deisred configuration
        """
        commands = []

        if interface_type in ('loopback', 'portchannel', 'svi'):
            commands.append('no interface {0}'. format(w['name']))
            commands.extend(self._state_merged(w, obj_in_have, interface_type))
        else:
            commands.append('default interface {0}'.format(w['name']))
            commands.extend(self._state_merged(w, obj_in_have, interface_type))

        return commands

    def _state_overridden(self, w, obj_in_have, interface_type):
        """ The command generator when state is overridden

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the deisred configuration
        """
        commands = []

        for h in have:
            name = h['name']
            obj_in_want = search_obj_in_list(name, want)
            if not obj_in_want:
                interface_type = get_interface_type(name)

                # Remove logical interfaces
                if interface_type in ('loopback', 'portchannel', 'svi'):
                    commands.append('no interface {0}'.format(name))
                elif interface_type == 'ethernet':
                    default = True
                    if h['enable'] is True:
                        keys = ('description', 'mode', 'mtu', 'speed', 'duplex', 'ip_forward', 'fabric_forwarding_anycast_gateway')
                        for k, v in iteritems(h):
                            if k in keys:
                                if h[k] is not None:
                                    default = False
                                    break
                    else:
                        default = False

                    if default is False:
                        # Put physical interface back into default state
                        commands.append('default interface {0}'.format(name))

        for w in want:
            name = w['name']
            interface_type = get_interface_type(name)
            obj_in_have = search_obj_in_list(name, have)
            commands.extend(self._state_merged(w, obj_in_have, interface_type))

        return commands

    def _state_merged(self, w, obj_in_have, interface_type):
        """ The command generator when state is merged

        :rtype: A list
        :returns: the commands necessary to merge the provided into
                  the current configuration
        """
        commands = []

        args = ('speed', 'description', 'duplex', 'mtu')
        name = w['name']
        mode = w.get('mode')
        ip_forward = w.get('ip_forward')
        fabric_forwarding_anycast_gateway = w.get('fabric_forwarding_anycast_gateway')
        enable = w.get('enable')

        if name:
            interface = 'interface ' + name

        if not obj_in_have:
            commands.append(interface)
            if interface_type in ('ethernet', 'portchannel'):
                if mode == 'layer2':
                    commands.append('switchport')
                elif mode == 'layer3':
                    commands.append('no switchport')

            if enable is True:
                commands.append('no shutdown')
            elif enable is False:
                commands.append('shutdown')

            if ip_forward == 'enable':
                commands.append('ip forward')
            elif ip_forward == 'disable':
                commands.append('no ip forward')

            if fabric_forwarding_anycast_gateway is True:
                commands.append('fabric forwarding mode anycast-gateway')
            elif fabric_forwarding_anycast_gateway is False:
                commands.append('no fabric forwarding mode anycast-gateway')

            for item in args:
                candidate = w.get(item)
                if candidate:
                    commands.append(item + ' ' + str(candidate))

        else:
            if interface_type in ('ethernet', 'portchannel'):
                if mode == 'layer2' and mode != obj_in_have.get('mode'):
                    self._add_command_to_interface(interface, 'switchport', commands)
                elif mode == 'layer3' and mode != obj_in_have.get('mode'):
                    self._add_command_to_interface(interface, 'no switchport', commands)

            if enable is True and enable != obj_in_have.get('enable'):
                self._add_command_to_interface(interface, 'no shutdown', commands)
            elif enable is False and enable != obj_in_have.get('enable'):
                self._add_command_to_interface(interface, 'shutdown', commands)

            if ip_forward == 'enable' and ip_forward != obj_in_have.get('ip_forward'):
                self._add_command_to_interface(interface, 'ip forward', commands)
            elif ip_forward == 'disable' and ip_forward != obj_in_have.get('ip forward'):
                self._add_command_to_interface(interface, 'no ip forward', commands)

            if (fabric_forwarding_anycast_gateway is True and obj_in_have.get('fabric_forwarding_anycast_gateway') is False):
                self._add_command_to_interface(interface, 'fabric forwarding mode anycast-gateway', commands)

            elif (fabric_forwarding_anycast_gateway is False and obj_in_have.get('fabric_forwarding_anycast_gateway') is True):
                self._add_command_to_interface(interface, 'no fabric forwarding mode anycast-gateway', commands)

            for item in args:
                candidate = w.get(item)
                if candidate and candidate != obj_in_have.get(item):
                    cmd = item + ' ' + str(candidate)
                    self._add_command_to_interface(interface, cmd, commands)

            # if the mode changes from L2 to L3, the admin state
            # seems to change after the API call, so adding a second API
            # call to ensure it's in the desired state.
            if name and interface_type == 'ethernet':
                if mode and mode != obj_in_have.get('mode'):
                    enable = w.get('enable') or obj_in_have.get('enable')
                    if enable is True:
                        commands.append(self._get_admin_state(enable))

        return commands

    def _state_deleted(self, w, obj_in_have, interface_type):
        """ The command generator when state is deleted

        :rtype: A list
        :returns: the commands necessary to remove the current configuration
                  of the provided objects
        """
        commands = []
        if not obj_in_have or interface_type == 'unknown':
            return commands

        interface = 'interface ' + w['name']

        if 'description' in obj_in_have:
            self._remove_command_from_interface(interface, 'description', commands)
        if 'enable' in obj_in_have and obj_in_have['enable'] is False:
            # if enable is False set enable as True which is the default behavior
            self._remove_command_from_interface(interface, 'shutdown', commands)

        if interface_type == 'ethernet':
            if 'mode' in obj_in_have and obj_in_have['mode'] != 'layer2':
                # if mode is not layer2 set mode as layer2 which is the default behavior
                self._remove_command_from_interface(interface, 'switchport', commands)

            if 'speed' in obj_in_have:
                self._remove_command_from_interface(interface, 'speed', commands)
            if 'duplex' in obj_in_have:
                self._remote_command_from_interface(interface, 'duplex', commands)

        if interface_type in ('ethernet', 'portchannel', 'svi'):
            if 'mtu' in obj_in_have:
                self._remove_command_from_interface(interface, 'mtu', commands)

        if interface_type in ('ethernet', 'svi'):
            if 'ip_forward' in obj_in_have:
                self._remove_command_from_interface(interface, 'ip forward', commands)
            if 'fabric_forwarding_anycast_gateway' in obj_in_have:
                self._remove_command_from_interface(interface, 'fabric forwarding anycast gateway', commands)

        return commands

    def _remove_command_from_interface(self, interface, cmd, commands):
        if interface not in commands:
            commands.insert(0, interface)
        commands.append('no %s' % cmd)
        return commands

    def _get_admin_state(self, enable):
        command = ''
        if enable is True:
            command = 'no shutdown'
        elif enable is False:
            command = 'shutdown'
        return command

    def _add_command_to_interface(self, interface, cmd, commands):
        if interface not in commands:
            commands.insert(0, interface)
        commands.append(cmd)
