import re 
import subprocess
import os
import datetime
import time
import sys
import humanize
import ftplib
import pyAesCrypt
import requests
import logging
import math
import natsort
import shutil
from pprint import pprint
from croniter import croniter

from src import settings
from src import docker
from src.database import Database, DatabaseType



def main():

    # Load config
    config, global_labels = settings.read()
    docker_client = docker.get_client()

    # Setup Logger
    logging.basicConfig(level=config.logginglevel,
                        format='%(asctime)s %(levelname)s: %(message)s')

    

    def nextRun(silent=False):
        iter = croniter(config.schedule, datetime.datetime.now())
        nextrun = iter.get_next(datetime.datetime)
        if not silent:
            logging.info(f"Next backup cycle will be at {nextrun}")
        return nextrun

    logging.info(f"+++ Welcome to pyd2b2! +++")

    if config.singlerun:
        logging.info("SCHEDULE value is empty, fallback to one-time backup")
    else:
        if config.startup:
            nextrun = datetime.datetime.now()
        else:
            nextrun = nextRun(True)
        
        logging.info(f"Schedule is activated. Next backup cycle will be at {nextrun}")

    # clean up old networks
    logging.debug("Clean up old networks...")
    oldnetworks = docker_client.networks.list(names=config.helper_network_name,greedy=True)
    if len(oldnetworks):
        for i, oldnetwork in enumerate(oldnetworks):
            logging.debug(f"Remove network {i+1}/{len(oldnetworks)}: {oldnetwork.id}...")
            for i, connected_container in enumerate(oldnetwork.containers):
                logging.debug(f"Remove network from container {i+1}/{len(oldnetwork.containers)}: {connected_container.name}...")
                docker_client.networks.get(oldnetwork.id).disconnect(connected_container.id,force=True)
            docker_client.networks.get(oldnetwork.id).remove()
        logging.debug("Clean up old networks done!")
    else:
        logging.debug(f"Nothing to clean up")

    while True:

        if config.schedule:
            diff = nextrun-datetime.datetime.now()
            #logging.debug(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {nextrun} | {diff.total_seconds()}")
            if diff.total_seconds() >= 0:
                time.sleep(5)
                continue

        containers = docker_client.containers.list(
            filters = {
                "label": settings.LABEL_PREFIX + "enable=true"
            }
        )

        if len(containers):
            logging.info(f"Starting backup cycle with {len(containers)} container(s)...")

            if config.hc_uuid != "":
                hcurl = config.hc_ping_url + config.hc_uuid + "/start"
                logging.debug(f"Start time measuring to Healthchecks.io ({hcurl})...")
                try:
                    requests.get(hcurl, timeout=10)

                except requests.RequestException as e:
                    logging.error(f"Failed to start time measuring to Healthchecks.io. Error Output: {e}")

            own_container_id = subprocess.check_output("basename $(cat /proc/1/cpuset)", shell=True, text=True).strip()
            successful_containers = 0

            network = docker_client.networks.create(config.helper_network_name)
            network.connect(own_container_id)

            container_filter = [x.strip() for x in config.container_filter.split(',') if x]

            if len(container_filter) > 0:
                logging.info(f"Container filter is active! Process only this names: {container_filter}")
                # Removes all containers from the list, which are not included in the filter
                containers = [x for x in containers if x.name in container_filter]

            for i, container in enumerate(containers):
                database = Database(container, global_labels)

                logging.info("[{}/{}] Processing container {} {} ({})".format(
                    i + 1, 
                    len(containers), 
                    container.short_id,
                    container.name,
                    database.type.name
                ))

                if database.type == DatabaseType.influxdb:
                    logging.debug("Login http://database-backup-target:{} using Token".format(database.port))
                else:
                    logging.debug("Login {}@database-backup-target:{} using Password: {}".format(database.username, database.port, "YES" if len(database.password) > 0 else "NO"))

                if database.type == DatabaseType.unknown:
                    logging.error("Cannot read database type. Please specify via label.")

                network.connect(container, aliases = ["database-backup-target"])
                outFile = "{}/{}_{}".format(config.dump_dir, container.name, time.strftime("%Y%m%dT%H%M%S"))
                error_code = 0
                error_text = ""
                error_stdout = ""

                logging.debug("Dumping all databases...")
                
                try:
                    env = os.environ.copy()

                    if database.type == DatabaseType.mysql or database.type == DatabaseType.mariadb:
                        outFile = outFile + ".sql"
                        subprocess.run(
                            ("mysqldump --host=database-backup-target --port={} --user={} --password={}"
                            " --all-databases"
                            " --ignore-database=mysql"
                            " --ignore-database=information_schema"
                            " --ignore-database=performance_schema"
                            " > {}").format(
                                database.port,
                                database.username, 
                                database.password,
                                outFile),
                            shell=True,
                            text=True,
                            capture_output=True,
                            env=env,
                        ).check_returncode()
                    elif database.type == DatabaseType.postgres:
                        outFile = outFile + ".sql"
                        env["PGPASSWORD"] = database.password
                        subprocess.run(
                            ("pg_dumpall --host=database-backup-target --port={} --username={}"
                            " > {}").format(
                                database.port,
                                database.username, 
                                outFile),
                            shell=True,
                            text=True,
                            capture_output=True,
                            env=env
                        ).check_returncode()
                    elif database.type == DatabaseType.influxdb:
                        subprocess.run(
                            ("influx backup --host http://database-backup-target:{} --token {} {}/").format(
                                database.port,
                                database.token,
                                outFile
                                ),
                            shell=True,
                            text=True,
                            capture_output=True,
                            env=env
                        ).check_returncode()
                except subprocess.CalledProcessError as e:
                    error_code = e.returncode
                    error_text = f"\n{e.stderr.strip()}".replace('\n', '\n> ').strip()
                    error_stdout = f"\n{e.stdout.strip()}".replace('\n', '\n> ').strip()

                network.disconnect(container)

                if error_code > 0:
                    logging.error(f"Return Code: {error_code}; Error Output:")
                    logging.error(f"{error_text}")
                    logging.debug(f"Standard Output:")
                    logging.debug(f"{error_stdout}")
                    
                    if os.path.exists(outFile):
                        if os.path.isdir(outFile):
                            shutil.rmtree(outFile)
                        else:
                            os.remove(outFile)
                else:
                    if (os.path.exists(outFile)):
                        noError = True
                        if os.path.isdir(outFile):
                            targetFile = outFile + ".tar.gz"
                            uncompressed_size = 0
                            for ele in os.scandir(outFile):
                                uncompressed_size+=os.stat(ele).st_size
                        else:
                            targetFile = outFile + ".gz"
                            uncompressed_size = os.path.getsize(outFile)
                        if (database.compress or os.path.isdir(outFile)) and uncompressed_size > 0:
                            logging.debug(f"Compressing {humanize.naturalsize(uncompressed_size)}...")
                            if os.path.exists(targetFile):
                                os.remove(targetFile)

                            try:
                                if os.path.isdir(outFile):
                                    subprocess.check_output("cd {} && tar cvzf {} *".format(outFile, targetFile), shell=True)
                                else:
                                    subprocess.check_output("gzip {}".format(outFile), shell=True)
                            except Exception as e:
                                logging.error(f"Error Output: {e}")
                                noError = False

                            if noError and os.path.isdir(outFile):
                                shutil.rmtree(outFile)

                            outFile = targetFile
                            
                            compressed_size = os.path.getsize(outFile)
                        else:
                            database.compress = False

                        
                        if noError and database.encryption_passphrase != "":
                            filesize = os.path.getsize(outFile)
                            logging.debug(f"Encrypting {humanize.naturalsize(filesize)}...")

                            bufferSize = 64 * 1024
                            outFileEncrypted = outFile + ".aes"
                        
                            try:
                                pyAesCrypt.encryptFile(outFile, outFileEncrypted, database.encryption_passphrase, bufferSize)
                                
                                os.remove(outFile)
                                outFile = outFileEncrypted

                                compressed_size = os.path.getsize(outFileEncrypted)

                            except Exception as e:
                                logging.error(f"Error Output: {e}")
                                noError = False

                        if noError:
                            os.chown(outFile, config.dump_uid, config.dump_gid) # pylint: disable=maybe-no-member

                            successful_containers += 1
                            logging.info("SUCCESS. File: {} ({}{})".format(outFile, 
                                                                        humanize.naturalsize(uncompressed_size), 
                                                                        ", " + humanize.naturalsize(compressed_size) + " compressed" if database.compress else "")
                                                                    )

            network.disconnect(own_container_id)
            network.remove()

            # Clean up old backups
            cleanup(config)

            all_backups_successfull = (successful_containers == len(containers))
            msg = f"Finished backup cycle. {successful_containers}/{len(containers)} successful."

            # Send request on success
            if config.success_url != "" and all_backups_successfull:
                
                logging.debug(f"Send request to success url ({config.success_url})...")
                try:
                    requests.get(config.success_url, timeout=10)
                except requests.RequestException as e:
                    logging.error(f"Send request to success url ({config.success_url}) failed. Error Output: {e}")
            
            if config.hc_uuid != "":
                hcurl = config.hc_ping_url + config.hc_uuid + ("/fail" if not all_backups_successfull else "")
                data = msg
                logging.debug(f"Send ping to Healthchecks.io ({hcurl})...")
                try:
                    requests.put(hcurl, data=data, timeout=10)

                except requests.RequestException as e:
                    logging.error(f"Sending a ping to Healthchecks.io failed. Error Output: {e}")

            logging.info(msg)
        else:
            logging.info("No databases to backup")

        if config.singlerun:
            logging.info("Program terminated")
            sys.exit()
        elif config.schedule:
            nextrun = nextRun()

def cleanup(config):
    logging.info("Clean up old backups (delete older than {} day{}, but keep at least {} file{})".format(
        config.delete_days,
        ("s" if config.delete_days > 1 else ""),
        config.keep_min,
        ("s" if config.keep_min > 1 else "")
    ))
    files = [f for f in natsort.natsorted(os.listdir(config.dump_dir), reverse=True) if os.path.isfile(os.path.join(config.dump_dir, f))]
    logging.debug(f"Found {len(files)} files")
    filelist = {}
    for f in files:
        #logging.info(f"Parse filename {f}")
        match = re.search('(.*)_(\d{4}\d{2}\d{2}T\d{2}\d{2}\d{2})', f)
        filedate = datetime.datetime.strptime(match.group(2), '%Y%m%dT%H%M%S')
        filedate_diff = datetime.datetime.now() - filedate
        days = int(math.floor(filedate_diff.days))
        #logging.info("DB: {} Date: {} Days: {}".format(match.group(1), filedate.strftime("%Y-%m-%d %H:%M:%S"), days))
        if not match.group(1) in filelist:
            filelist[match.group(1)] = []
        filelist[match.group(1)].append({'filename': f, 'date': filedate.strftime("%Y-%m-%d %H:%M:%S"), 'days': days})
    
    #pprint(filelist)
    count_container = 0
    count_deleted = 0
    count_dumps_total = 0
    for name in filelist:
        count_container += 1
        
        logging.debug(f"[{count_container:02d}/{len(filelist):02d}] Clean dumps from container {name}")

        count_dumps = 0
        for details in filelist[name]:
            count_dumps_total += 1
            count_dumps += 1

            fullpath = os.path.join(config.dump_dir, details['filename'])

            delete = False
            if details['days'] >= config.delete_days and count_dumps > config.keep_min:
                delete = True
                count_deleted += 1
                try:
                    os.remove(fullpath)
                except Exception:
                    logging.exception(f"Failed to delete dump {fullpath}")
            
            

            # logging.debug("[{:03d}/{:03d}] {} = {:03d} days ({}) -> Delete: {}".format(
            #     count_dumps,
            #     len(filelist[name]),
            #     details['date'],
            #     details['days'],
            #     fullpath,
            #     delete)
            # )
    logging.info(f"Deleted {count_deleted} of {count_dumps_total} dumps")

            
        
        

if __name__ == '__main__':
    main()
