from enum import Enum
import re
import distutils.util

import docker

from . import settings

class DatabaseType(Enum):
  unknown = -1
  auto = 0
  mysql = 1
  mariadb = 2
  postgres = 3
  influxdb = 4

KNOWN_IMAGES = {
  # MySQL
  "mysql": DatabaseType.mysql,
  "bitnami/mysql": DatabaseType.mysql,
  "mysql/mysql-server": DatabaseType.mysql,
  # MariaDB
  "mariadb": DatabaseType.mariadb,
  "bitnami/mariadb": DatabaseType.mariadb,
  "linuxserver/mariadb": DatabaseType.mariadb,
  "mariadb/server": DatabaseType.mariadb,
  # Postgres
  "postgres": DatabaseType.postgres,
  "bitnami/postgresql": DatabaseType.postgres,
  # InfluxDB 2.0
  "influxdb": DatabaseType.influxdb,
}

TYPE_DEFAULTS = {
  DatabaseType.unknown: {
    "port": 0,
  },
  DatabaseType.mysql: {
    "port": 3306,
  },
  DatabaseType.mariadb: {
    "port": 3306,
  },
  DatabaseType.postgres: {
    "port": 5432,
  },
  DatabaseType.influxdb: {
    "port": 8086,
  }
}

class Database:
  IMAGE_REGEX = re.compile("^(.+?)(?::.+)?$")

  def __init__(self, container, global_labels):
    self._load_labels(global_labels)
    local_labels = self._get_labels_from_container(container)
    self._load_labels(local_labels)
    self._resolve_labels(container)

  def _load_labels(self, values):
    if "enable" in values: self.enable = values["enable"]
    if "type" in values: self.type = values["type"]
    if "port" in values: self.port = values["port"]
    if "username" in values: self.username = values["username"]
    if "password" in values: self.password = values["password"]
    if "token" in values: self.token = values["token"]
    if "compress" in values: self.compress = values["compress"]
    if "encryption_passphrase" in values: self.encryption_passphrase = values["encryption_passphrase"]

  def _get_labels_from_container(self, container):
    labels = {}

    for key, value in container.labels.items():
      if key.startswith(settings.LABEL_PREFIX):
        short_key = key[len(settings.LABEL_PREFIX):len(key)]
        labels[short_key] = value

    return labels

  def _resolve_labels(self, container):
    try:
      self.type = DatabaseType[self.type]
    except AttributeError:
      self.type = DatabaseType.unknown

    if self.type == DatabaseType.auto:
      for tag in container.image.tags:
        matches = self.IMAGE_REGEX.match(tag)
        search_part = matches.group(1)
        matched_type = KNOWN_IMAGES.get(search_part, None)
        if matched_type != None:
          self.type = matched_type
          break
      if self.type == DatabaseType.auto:
        self.type = DatabaseType.unknown

    defaults = TYPE_DEFAULTS.get(self.type)

    if self.port == "auto": 
      self.port = defaults.get("port")
    else:
      self.port = int(self.port)
    
    self.compress = distutils.util.strtobool(self.compress)
