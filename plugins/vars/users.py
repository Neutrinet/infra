#!/usr/bin/env python3

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    vars: users
    version_added: "2.10"
    short_description: Populate the users variable with the list of users per hosts or groups
    requirements:
        - whitelist in configuration
    description:
        - Loads the list of users with SSH keys located in host_files or group_files directories
        - SSH keys are restricted by extension to .pub
        - Additionnal user options can be defined in a file main.yml at the same location of the SSH keys
        - Starting in 2.10, this plugin requires whitelisting and is whitelisted by default.
    options:
      user_shell:
        default: /bin/bash
        description:
          - Default shell of the users
        ini:
          - key: shell
            section: vars_users
        env:
          - name: ANSIBLE_VARS_PLUGIN_USER_SHELL
        type: str
      user_home:
        default: "/home/{}"
        description:
          - Default home location
          - The '{}' is optional and is replaced by the username
        ini:
          - key: home
            section: vars_users
        env:
          - name: ANSIBLE_VARS_PLUGIN_USER_HOME
        type: str
      user_groups:
        default: ["sudo"]
        description:
          - List of default user groups
        ini:
          - key: groups
            section: vars_users
        env:
          - name: ANSIBLE_VARS_PLUGIN_USER_GROUPS
        type: list
      user_forbidden_keys:
        default: ["name", "ssh_keys"]
        description:
          - List of keys from the user config that cannot be overriden
        ini:
          - key: forbidden_keys
            section: vars_users
        env:
          - name: ANSIBLE_VARS_PLUGIN_USER_FORBIDDEN_KEYS
        type: list
      ssh_key_extensions:
        default: [".pub"]
        description:
          - "Check all of these extensions when looking for SSH key files"
          - "These files should be valid SSH public keys."
        ini:
          - key: ssh_key_extensions
            section: vars_users
        env:
          - name: ANSIBLE_VARS_PLUGIN_SSH_KEY_EXTENSIONS
        type: list
      user_config_filename:
        default: main.yml
        description:
          - Filename containing the user config
        ini:
          - key: config_filename
            section: vars_users
        env:
          - name: ANSIBLE_VARS_PLUGIN_USER_CONFIG_FILENAME
'''

import glob
import os

from ansible import constants as C
from ansible.errors import AnsibleParserError
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.vars import BaseVarsPlugin
from ansible.inventory.host import Host
from ansible.inventory.group import Group
from ansible.utils.vars import combine_vars

FOUND = {}


class VarsModule(BaseVarsPlugin):
    REQUIRES_WHITELIST = False

    def get_vars(self, loader, path, entities, cache=True):
        if not isinstance(entities, list):
            entities = [entities]

        super(VarsModule, self).get_vars(loader, path, entities)

        DEFAULT_USER_SHELL = self.get_option("user_shell")
        DEFAULT_USER_HOME = self.get_option("user_home")
        DEFAULT_USER_GROUPS = self.get_option("user_groups")
        USER_CONFIG_FORBIDDEN_KEYS = self.get_option("user_forbidden_keys")
        SSH_KEY_EXTENSIONS = self.get_option("ssh_key_extensions")
        USER_CONFIG_FILENAME = self.get_option("user_config_filename")

        users = []
        for entity in entities:
            if isinstance(entity, Host):
                entity_type_dir = 'host_files'
            elif isinstance(entity, Group):
                entity_type_dir = 'group_files'
            else:
                raise AnsibleParserError("Supplied entity must be Host or Group, got %s instead" % (type(entity)))
            
            entity_files_dir = os.path.join(path, entity_type_dir, entity.name)
            users_dir = os.path.join(entity_files_dir, "users")
            
            if not os.path.isdir(users_dir):
                self._display.verbose("No such '%s' directory: Skipping" % users_dir, caplevel=1)
                continue

            usernames = os.listdir(users_dir)
            self._display.verbose("Found the following usernames: %s" % usernames)
            for username in usernames:
                user_ssh_keys = []
                user = {
                    "name": username,
                    "shell": DEFAULT_USER_SHELL,
                    "password": '*',
                    "groups": DEFAULT_USER_GROUPS,
                    "state": "present",
                    "home": DEFAULT_USER_HOME.format(username),
                    "ssh_keys": user_ssh_keys
                }
                user_dir = os.path.join(users_dir, username)
                if not os.path.isdir(user_dir):
                    self._display.warning("No such directory '%s' for %s user" % (user_dir, username))
                    continue

                for ssh_key_extension in SSH_KEY_EXTENSIONS:
                    pattern = '*' + ssh_key_extension
                    ssh_key_path_pattern = os.path.join(user_dir, pattern)
                    for ssh_key_path in glob.glob(ssh_key_path_pattern):
                        ssh_key = loader.load_from_file(ssh_key_path,
                                                        cache=True,
                                                        unsafe=True)
                        user_ssh_keys.append(ssh_key)

                user_config_path = os.path.join(user_dir, USER_CONFIG_FILENAME)
                if os.path.isfile(user_config_path):
                    user_config = loader.load_from_file(user_config_path,
                                                        cache=True,
                                                        unsafe=True)
                    for forbidden_key in USER_CONFIG_FORBIDDEN_KEYS:
                        if forbidden_key in user_config:
                            self._display.warning("Found forbidden key '%s' in %s user config: Ignoring" % (forbidden_key, username))
                            del user_config[forbidden_key]
                    user.update(user_config)

                users.append(user)

        users_var = {}
        if len(users) > 0:
            users_var = {"users": users}
        return users_var