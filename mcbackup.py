from mcrcon import MCRcon
import json
import os.path
import time
from datetime import datetime, timedelta
import zipfile
import re

class Config:
    world_location = "./"
    backup_location = "./"
    rcon_host = "localhost";
    rcon_port = 25575;
    rcon_password = "";
    backup_frequency = ["weekly"]

    @classmethod
    def set_from_dict(cls, dict_values: dict):
        for key, value in dict_values.items():
            if hasattr(cls, key):
                setattr(cls, key, value)

    @classmethod
    def get_dict(cls):
        return {key: value for key, value in cls.__dict__.items() if not key.startswith('__') and not callable(value) and not isinstance(value, (classmethod, staticmethod))}

config_path = 'config.json'
time_format = "%Y%m%d-%H%M%S"
backup_regex = ".*{0}_(.*).zip"

time_deltas = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": timedelta(weeks=4),
    "quarterly": timedelta(weeks=13),
    "yearly": timedelta(days=365)
}

if (os.path.isfile(config_path)):
    with open(config_path) as f:
        d = json.load(f)
        Config.set_from_dict(d)
else:
    with open(config_path, 'w') as f:
        json.dump(Config.get_dict(), f, indent=4)

def log(str):
    mcr.command("say " + str)
    print(str)

def command(str):
    response = mcr.command(str)
    log(response);

def zipDir(dir: str, zip_handle: zipfile.ZipFile):
    for root, dirs, files in os.walk(dir):
        for file in files:
            zip_handle.write(os.path.join(root, file), 
                    os.path.relpath(os.path.join(root, file), 
                                    os.path.join(dir, '..')))


def backup(tag: str):
    timestr = datetime.strftime(now, time_format)
    zip_name = "backup_{0}_{1}.zip".format(tag, timestr)
    with zipfile.ZipFile(os.path.join(Config.backup_location, zip_name), 'w', zipfile.ZIP_DEFLATED) as zip_handle:
        zipDir(os.path.join(Config.world_location,"world"), zip_handle)
        zipDir(os.path.join(Config.world_location,"world_nether"), zip_handle)
        zipDir(os.path.join(Config.world_location,"world_the_end"), zip_handle)
    log("Backup saved: " + zip_name)

def try_backup(tag: str, rate: timedelta):
    for root, dirs, files in os.walk(Config.backup_location):
        for file in files:
            pattern = backup_regex.format(tag)
            match = re.search(pattern,file)
            if match:
                backup_time = datetime.strptime(match.group(1), time_format)
                time_delta = now - rate
                if (time_delta <= backup_time):
                    print("Backup tag: {0} within given rate. Skipping.".format(tag))
                    return;
                else:
                    os.remove(os.path.join(Config.backup_location, match.string))
    backup(tag)

now = datetime.now()

with MCRcon(Config.rcon_host, Config.rcon_password, port=Config.rcon_port) as mcr:
    log("Saving Backups")
    command("save-all")
    time.sleep(5);
    command("save-off")
    for rate in Config.backup_frequency:
        delta = time_deltas.get(rate)
        if (delta is None):
            print("Tag: {0} is not a valid time rate. Tag must be one of the following: {1}".format(rate, list(time_deltas)))
            continue
        try_backup(rate, delta)
    command("save-on")
    log("Backups complete")
