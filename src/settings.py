import os
import distutils.util
from croniter import croniter
import logging

LABEL_PREFIX = "foorschtbar.dbbackup."

CONFIG_DEFAULTS = {
    "debug": "false",
    "dump_uid": "0",
    "dump_gid": "0",
    "success_url": "",
    "hc_uuid": "",
    "hc_ping_url": "https://hc-ping.com/",
    "schedule": "",
    "helper_network_name": "dbbackup-helpernet",
}

LABEL_DEFAULTS = {
    "enable": "false",
    "username": "root",
    "password": "",
    "type": "auto",
    "port": "auto",
    "compress": "true",
    "encryption_passphrase": "",
}

class Config:
    def __init__(self, values):
        self.debug = distutils.util.strtobool(values["debug"])
        if self.debug:
            self.logginglevel = logging.DEBUG
        else:
            self.logginglevel = logging.INFO
        self.dump_uid = int(values["dump_uid"])
        self.dump_gid = int(values["dump_gid"])
        self.success_url = str(values["success_url"])
        self.hc_uuid = str(values["hc_uuid"])
        self.hc_ping_url = str(values["hc_ping_url"])
        self.schedule = str(values["schedule"])
        if self.schedule and not croniter.is_valid(self.schedule):
            raise AttributeError("Invalid schedule syntax")

        if self.schedule:
            self.singlerun = False
        else: 
            self.singlerun = True

        self.helper_network_name = str(values["helper_network_name"])

def read():
    config_values = {}
    label_values = {}

    for key, default_value in CONFIG_DEFAULTS.items():
        env_name = _create_env_name(key)
        config_values[key] = os.getenv(env_name, default_value)

    for key, default_value in LABEL_DEFAULTS.items():
        env_name = _create_env_name(key, "global")
        label_values[key] = os.getenv(env_name, default_value)

    return Config(config_values), label_values

def _create_env_name(name, prefix = ""):
    if len(prefix) > 0:
        prefix = prefix + "."
    return "{}{}".format(prefix, name).upper().replace(".", "_")