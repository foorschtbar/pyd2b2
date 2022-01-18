# pyd2b2 - Python Docker Database Backup

[
![](https://img.shields.io/docker/v/foorschtbar/pyd2b2?style=plastic&sort=date)
![](https://img.shields.io/docker/pulls/foorschtbar/pyd2b2?style=plastic)
![](https://img.shields.io/docker/stars/foorschtbar/pyd2b2?style=plastic)
![](https://img.shields.io/docker/image-size/foorschtbar/pyd2b2?style=plastic)
](https://hub.docker.com/repository/docker/foorschtbar/pyd2b2)

[
![](https://img.shields.io/github/workflow/status/foorschtbar/pyd2b2/Build%20Docker%20Images?style=plastic)
![](https://img.shields.io/github/languages/top/foorschtbar/pyd2b2?style=plastic)
![](https://img.shields.io/github/last-commit/foorschtbar/pyd2b2?style=plastic)
![](https://img.shields.io/github/license/foorschtbar/pyd2b2?style=plastic)
](https://github.com/foorschtbar/pyd2b2)

**Py**thon **D**ocker **D**ata**b**ase **B**ackup is a dockerized service to automatically backup all of your database containers.

- GitHub: [foorschtbar/pyd2b2](https://github.com/foorschtbar/pyd2b2)
- Docker Hub: [foorschtbar/pyd2b2](https://hub.docker.com/r/foorschtbar/pyd2b2)

## Supported Databases

- MySQL/MariaDB
- PostgreSQL
- InfluxDB 2.0 (64-bit only)

## Service Configuration

Configure the backup service by specifying environment variables:

| Name                  | Default                | Description                                                                                                                                               |
| --------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TZ`                  | `UTC`                  | Time zone for schedule and times in log messages                                                                                                          |
| `SCHEDULE`            | (none)                 | Backup interval in [cron like format](http://en.wikipedia.org/wiki/Cron). If _empty_ or _not set_, the cycle runs only once (one-time backup).            |
| `STARTUP`             | `false`                | Backup all databases at startup.                                                                                                                          |
| `SUCCESS_URL`         | (none)                 | A url who called after every successfull backup cycle                                                                                                     |
| `HC_UUID`             | (none)                 | Insert a [HealthChecks.io](https://healthchecks.io/) UUID for monitoring                                                                                  |
| `HC_PING_URL`         | `https://hc-ping.com/` | [HealthChecks.io](https://healthchecks.io/) Ping Server URL if you run your own server                                                                    |
| `DEBUG`               | `false`                | Increased output                                                                                                                                          |
| `DUMP_UID`            | `-1`                   | UID of dump files. `-1` means default (docker executing user)                                                                                             |
| `DUMP_GID`            | `-1`                   | GID of dump files. `-1` means default (docker executing user)                                                                                             |
| `DUMP_DIR`            | `/dumps`               | Folder where database dumps are saved                                                                                                                     |
| `DELETE_DAYS`         | `14`                   | Dump files older than this number of days should be deleted                                                                                               |
| `KEEP_MIN`            | `20`                   | Number of dump files to keep for each container at least                                                                                                  |
| `CONTAINER_FILTER`    | (none)                 | For testing purposes: A comma-separated list of container names. Filter all containers that already have the `enable`-label. Example: `app-db, database2` |
| `HELPER_NETWORK_NAME` | `pyd2b2-helpernet`     | Name of the temporary created network that pyd2b2 uses to connect to containers                                                                           |

You can also define global default values for all container specific labels. Do this by prepending the label name by `GLOBAL_`. For example, to provide a default username, you can set a default value for `foorschtbar.pyd2b2.username` by specifying the environment variable `GLOBAL_USERNAME`. See next chapter for reference.

## Database Configuration

Configure each database container by specifying labels. Every label must be prefixed by `foorschtbar.pyd2b2.`:

| Name                    | Default | Description                                                                                                                                                            |
| ----------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `enable`                | `false` | Enable backup for this container                                                                                                                                       |
| `type`                  | `auto`  | Specify type of database. Possible values: `auto, mysql, mariadb, postgres, influxdb`. Auto tries to get the type from the image name (for specific well known images) |
| `username`              | `root`  | Login user                                                                                                                                                             |
| `password`              | (none)  | Login password                                                                                                                                                         |
| `token`                 | (none)  | InfluxDB 2.0 access token                                                                                                                                              |
| `port`                  | `auto`  | Port (inside container). Possible values: `auto` or a valid port number. Auto gets the default port corresponding to the type.                                         |
| `compress`              | `true`  | Compress SQL Dump with gzip                                                                                                                                            |
| `encryption_passphrase` | _empty_ | A passphrase to encrypt the backup files. No encryption if empty.                                                                                                      |

## Example

Example docker-compose.yml:

```yml
version: "3"

services:
  db-backup: # backup service
    image: foorschtbar/pyd2b2
    environment:
      - TZ=Europe/Berlin
      - SCHEDULE=0 */12 * * *
      - STARTUP=true
      - GLOBAL_USERNAME=root
      - GLOBAL_ENCRYPTION_PASSPHRASE=secret-password
      - HC_UUID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  database1: # well known database image
    image: mariadb:latest
    environment:
      - MYSQL_ROOT_PASSWORD=secret-password
    labels:
      - foorschtbar.pyd2b2.enable=true

  database2: # custom database image
    image: user/my-database:latest
    environment:
      - DB_PASSWORD=secret-password
    labels:
      - foorschtbar.pyd2b2.enable=true
      - foorschtbar.pyd2b2.type=postgres
      - foorschtbar.pyd2b2.password=other-password
```

## Credits

Forked from [jan-di/docker-database-backup](https://github.com/jan-di/docker-database-backup)
Inspired by [kibatic/docker-mysql-backup](https://github.com/kibatic/docker-mysql-backup)
