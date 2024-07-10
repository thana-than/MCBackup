from mcrcon import MCRcon
import json
import os.path
import time
from datetime import datetime, timedelta
import zipfile
import re
import getopt, sys
import shutil

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


argumentList = sys.argv[1:]
verbose = False

options = "c:v"
long_options = ["config", "verbose"]

backup_zip = None

try:
    # Parsing argument
    arguments, values = getopt.getopt(argumentList, options, long_options)
    # checking each argument
    for currentArgument, currentValue in arguments:
        if currentArgument in ("-c", "--config"):
            config_path = currentValue
            print(f"Config path set to {currentValue}")
        elif currentArgument in ("-v", "--verbose"):
            verbose = True
            print("Verbose debugging enabled")
            
except getopt.error as err:
    # output error, and return with an error code
    print (str(err))


def test_path(path: str) :
    if (os.path.exists(path) or os.access(os.path.dirname(path), os.W_OK)):
        return

    print(f"ERROR: Path {path} is invalid.")
    sys.exit(1)

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

test_path(Config.backup_location)
test_path(Config.world_location)

def log(str):
    mcr.command("say " + str)
    print(str)

def command(str):
    response = mcr.command(str)
    log(response);

def zipDir(dir: str, zip_handle: zipfile.ZipFile):
    for root, dirs, files in os.walk(dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, os.path.join(dir, '..'))
            if (file == 'session.lock'): #ignore session.lock file
                continue;
            try:
                zip_handle.write(file_path, arcname)
                if verbose : print(f"Added {file_path} to zip as {arcname}")
            except PermissionError as e:
                print(f"PermissionError: {e} - {file_path}")
            except Exception as e:
                print(f"Error: {e} - {file_path}")


def backup(tag: str):
    timestr = datetime.strftime(now, time_format)
    zip_name = f"backup_{tag}_{timestr}.zip"
    zip_path = os.path.join(Config.backup_location, zip_name)
    global backup_zip
    if (backup_zip is None):
        backup_zip = zip_path
        print(f"Creating new zip {backup_zip}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_handle:
            zipDir(os.path.join(Config.world_location,"world"), zip_handle)
            zipDir(os.path.join(Config.world_location,"world_nether"), zip_handle)
            zipDir(os.path.join(Config.world_location,"world_the_end"), zip_handle)
    else:
        print(f"Copying from existing backup {backup_zip} to {zip_name}")
        shutil.copyfile(backup_zip,zip_path)
        
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
                    print(f"Backup tag: {tag} within given rate. Skipping.")
                    return;
                else:
                    os.remove(os.path.join(Config.backup_location, match.string))
    backup(tag)

now = datetime.now()

with MCRcon(Config.rcon_host, Config.rcon_password, port=Config.rcon_port) as mcr:
    log("Saving Backups")
    command("save-all")
    time.sleep(5);
    try:
        command("save-off")
        for rate in Config.backup_frequency:
            delta = time_deltas.get(rate)
            if (delta is None):
                print(f"Tag: {rate} is not a valid time rate. Tag must be one of the following: f{list(time_deltas)}")
                continue
            try_backup(rate, delta)
        command("save-on")
        log("Backups complete")
    except getopt.error as err:
        command("save-on") #ensure saving is turned on even if there's an error
        print (str(err))