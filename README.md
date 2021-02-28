# dbbackup-docker

[
  ![](https://img.shields.io/docker/v/foorschtbar/dbbackup?style=plastic&sort=date)
  ![](https://img.shields.io/docker/pulls/foorschtbar/dbbackup?style=plastic)
  ![](https://img.shields.io/docker/stars/foorschtbar/dbbackup?style=plastic)
  ![](https://img.shields.io/docker/image-size/foorschtbar/dbbackup?style=plastic)
  ![](https://img.shields.io/github/workflow/status/foorschtbar/dbbackup-docker/CI%20Workflow?style=plastic)
](https://hub.docker.com/repository/docker/foorschtbar/dbbackup)
[
  ![](https://img.shields.io/github/last-commit/foorschtbar/dbbackup-docker?style=plastic)
](https://github.com/foorschtbar/dbbackup-docker)


A dockerized service to automatically backup all of your database containers.

Docker Image: `foorschtbar/dbbackup`

## Service Configuration

Configure the backup service by specifying environment variables:

Name | Default | Description
--- | --- | ---
`TZ` | `UTC` | Time zone for schedule and times in log messages
`SCHEDULE` | (none) | Backup interval in [cron like format](http://en.wikipedia.org/wiki/Cron). If _empty_ or _not set_, the cycle runs only once (one-time backup).
`SUCCESS_URL` | (none) | A url who called after every successfull backup cycle
`HC_UUID`  | (none) | Insert a [HealthChecks.io](https://healthchecks.io/) UUID for monitoring
`HC_PING_URL`  | `https://hc-ping.com/` | [HealthChecks.io](https://healthchecks.io/) Ping Server URL if you run your own server
`VERBOSE` | `false` | Increased output
`DUMP_UID` | `-1` | UID of dump files. `-1` means default (docker executing user)
`DUMP_GID` | `-1` | GID of dump files. `-1` means default (docker executing user)

You can also define global default values for all container specific labels. Do this by prepending the label name by `GLOBAL_`. For example, to provide a default username, you can set a default value for `foorschtbar.dbbackup.username` by specifying the environment variable `GLOBAL_USERNAME`. See next chapter for reference.

## Database Configuration

Configure each database container by specifying labels. Every label must be prefixed by `foorschtbar.dbbackup.`:

Name | Default | Description
--- | --- | ---
`enable` | `false` | Enable backup for this container
`type` | `auto` | Specify type of database. Possible values: `auto, mysql, mariadb, postgres`. Auto tries to get the type from the image name (for specific well known images)
`username` | `root` | Login user
`password` | (none) | Login password
`port` | `auto` | Port (inside container). Possible values: `auto` or a valid port number. Auto gets the default port corresponding to the type.
`compress` | `false` | Compress SQL Dump with gzip
`encryption_passphrase` | _empty_ | A passphrase to encrypt the backup files. No encryption if empty.

## Example

Example docker-compose.yml:

```yml
version: "3"

services:
  db-backup: # backup service
    image: foorschtbar/dbbackup
    environment:
      - TZ=Europe/Berlin
      - SCHEDULE=0 */12 * * *
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
      - foorschtbar.dbbackup-docker.enable=true

  database2: # custom database image
    image: user/my-database:latest
    environment:
      - DB_PASSWORD=secret-password
    labels:
      - foorschtbar.dbbackup.enable=true
      - foorschtbar.dbbackup.type=postgres
      - foorschtbar.dbbackup.password=other-password
```

## Credits

Forked from [jan-di/docker-database-backup](https://github.com/jan-di/docker-database-backup)
Inspired by [kibatic/docker-mysql-backup](https://github.com/kibatic/docker-mysql-backup)