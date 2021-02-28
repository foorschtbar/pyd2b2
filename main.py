import re 
import subprocess
import os
import datetime
import time
import sys
import humanize
import ftplib
import dropbox
import pyAesCrypt
import requests
from croniter import croniter

from src import settings
from src import docker
from src.database import Database, DatabaseType

config, global_labels = settings.read()
docker_client = docker.get_client()

def nextRun(silent=False):
    iter = croniter(config.schedule, datetime.datetime.now())
    nextrun = iter.get_next(datetime.datetime)
    if not silent:
        print(f"Next run at {nextrun}")
    return nextrun

print(f"+++ Welcome to dbbackup! +++")

if config.singlerun:
    print("SCHEDULE value is empty, fallback to one-time backup")
else:
    nextrun = nextRun(True)
    print(f"Schedule is activated. First run at {nextrun}")

while True:

    if config.schedule:
        diff = nextrun-datetime.datetime.now()
        #print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {nextrun} | {diff.total_seconds()}")
        if diff.total_seconds() >= 0:
            time.sleep(5)
            continue

    containers = docker_client.containers.list(
        filters = {
            "label": settings.LABEL_PREFIX + "enable=true"
        }
    )

    if len(containers):
        print(f"Starting backup cycle with {len(containers)} container(s)..")

        if config.hc_uuid != "":
            hcurl = config.hc_ping_url + config.hc_uuid + "/start"
            if config.verbose: 
                    print(f"VERBOSE: Start time measuring to Healthchecks.io ({hcurl})...")
            try:
                requests.get(hcurl, timeout=10)

            except requests.RequestException as e:
                print(f"FAILED. Start time measuring to Healthchecks.io. Error Output: {e}")

        own_container_id = subprocess.check_output("basename $(cat /proc/1/cpuset)", shell=True, text=True).strip()
        successful_containers = 0

        network = docker_client.networks.create("docker-database-backup")
        network.connect(own_container_id)

        for i, container in enumerate(containers):
            database = Database(container, global_labels)

            print("[{}/{}] Processing container {} {} ({})".format(
                i + 1, 
                len(containers), 
                container.short_id,
                container.name,
                database.type.name
            ))

            if config.verbose:
                print("VERBOSE: Login {}@host:{} using Password: {}".format(database.username, database.port, "YES" if len(database.password) > 0 else "NO"))

            if database.type == DatabaseType.unknown:
                print("Cannot read database type. Please specify via label.")

            network.connect(container, aliases = ["database-backup-target"])
            outFile = "/dumps/{}_{}.sql".format(container.name, time.strftime("%Y%m%dT%H%M%S"))
            error_code = 0
            error_text = ""

            if config.verbose: 
                 print("VERBOSE: Dumping all databases...")
            
            try:
                env = os.environ.copy()

                if database.type == DatabaseType.mysql or database.type == DatabaseType.mariadb:
                    subprocess.run(
                        ("mysqldump --host=database-backup-target --user={} --password={}"
                        " --all-databases"
                        " --ignore-database=mysql"
                        " --ignore-database=information_schema"
                        " --ignore-database=performance_schema"
                        " > {}").format(
                            database.username, 
                            database.password,
                            outFile),
                        shell=True,
                        text=True,
                        capture_output=True,
                        env=env,
                    ).check_returncode()
                elif database.type == DatabaseType.postgres:
                    env["PGPASSWORD"] = database.password
                    subprocess.run(
                        ("pg_dumpall --host=database-backup-target --username={}"
                        " > {}").format(
                            database.username, 
                            outFile),
                        shell=True,
                        text=True,
                        capture_output=True,
                        env=env
                    ).check_returncode()
            except subprocess.CalledProcessError as e:
                error_code = e.returncode
                error_text = f"\n{e.stderr.strip()}".replace('\n', '\n> ').strip()

            network.disconnect(container)

            if error_code > 0:
                print(f"FAILED. Return Code: {error_code}; Error Output:")
                print(f"{error_text}")
            else:
                if (os.path.exists(outFile)):
                    noError = True
                    uncompressed_size = os.path.getsize(outFile)
                    if database.compress and uncompressed_size > 0:
                        if config.verbose: 
                            print(f"VERBOSE: Compressing {humanize.naturalsize(uncompressed_size)}...")
                        if os.path.exists(outFile + ".gz"):
                            os.remove(outFile + ".gz")

                        try:
                            subprocess.check_output("gzip {}".format(outFile), shell=True)
                        except Exception as e:
                            print(f"FAILED. Error Output: {e}")
                            noError = False

                        outFile = outFile + ".gz"
                        compressed_size = os.path.getsize(outFile)
                    else:
                        database.compress = False

                    
                    if noError and database.encryption_passphrase != "":
                        if config.verbose: 
                            filesize = os.path.getsize(outFile)
                            print(f"VERBOSE: Encrypting {humanize.naturalsize(filesize)}...")

                        bufferSize = 64 * 1024
                        outFileEncrypted = outFile + ".aes"
                    
                        try:
                            pyAesCrypt.encryptFile(outFile, outFileEncrypted, database.encryption_passphrase, bufferSize)
                            
                            os.remove(outFile)
                            outFile = outFileEncrypted

                            compressed_size = os.path.getsize(outFileEncrypted)

                        except Exception as e:
                            print(f"FAILED. Error Output: {e}")
                            noError = False

                    if noError:
                        os.chown(outFile, config.dump_uid, config.dump_gid) # pylint: disable=maybe-no-member

                        successful_containers += 1
                        print("SUCCESS. File: {} ({}{})".format(outFile, 
                                                                    humanize.naturalsize(uncompressed_size), 
                                                                    ", " + humanize.naturalsize(compressed_size) + " compressed" if database.compress else "")
                                                                )

        network.disconnect(own_container_id)
        network.remove()

        all_backups_successfull = (successful_containers == len(containers))
        msg = f"Finished backup cycle. {successful_containers}/{len(containers)} successful."

        # Send request on success
        if config.success_url != "" and all_backups_successfull:
            
            if config.verbose: 
                    print(f"VERBOSE: Send request to success url ({config.success_url})...")
            try:
                requests.get(config.success_url, timeout=10)
            except requests.RequestException as e:
                print(f"FAILED. Send request to success url ({config.success_url}) failed. Error Output: {e}")
        
        if config.hc_uuid != "":
            hcurl = config.hc_ping_url + config.hc_uuid if all_backups_successfull else hcurl + "/fail"
            data = msg
            if config.verbose: 
                    print(f"VERBOSE: Send ping to Healthchecks.io ({hcurl})...")
            try:
                requests.put(hcurl, data=data, timeout=10)

            except requests.RequestException as e:
                print(f"FAILED. Sending a ping to Healthchecks.io failed. Error Output: {e}")

        print(msg)
    else:
        print("No databases to backup")

    if config.singlerun:
        sys.exit()
    
    if config.schedule:
        nextrun = nextRun()
