from mcrcon import MCRcon
import json
import os.path
import time
from datetime import datetime, timedelta
import zipfile
import re
import getopt, sys
import shutil

#TODO dockerfile should run every x amount of time (smallest time period)
#TODO google upload? (through rclone?)
#TODO Config should be simpler and follow simple environment setting naming
#TODO dockerfile release automation
#TODO tar file
#TODO include option to save all instead of just worlds

class Config:
    WORLD_LOCATION = os.getenv('WORLD_LOCATION', "./")
    BACKUP_LOCATION = os.getenv('BACKUP_LOCATION', "./backup")
    RCON_HOST = os.getenv('RCON_HOST', "localhost")
    RCON_PORT = int(os.getenv('RCON_PORT', 25575))
    RCON_PASSWORD = os.getenv('RCON_PASSWORD', "")
    BACKUP_FREQUENCY = [x.strip() for x in os.getenv('BACKUP_FREQUENCY', "weekly").split(',')]

    @classmethod
    def set_from_dict(cls, dict_values: dict):
        for key, value in dict_values.items():
            if hasattr(cls, key):
                setattr(cls, key, value)

    @classmethod
    def get_dict(cls):
        return {key: value for key, value in cls.__dict__.items() if not key.startswith('__') and not callable(value) and not isinstance(value, (classmethod, staticmethod))}

    @classmethod
    def load_config(cls, config_path):
        if os.path.isfile(config_path):
            with open(config_path) as f:
                d = json.load(f)
                cls.set_from_dict(d)
        else:
            with open(config_path, 'w') as f:
                json.dump(cls.get_dict(), f, indent=4)

config_path = 'config.json'
time_format = "%Y-%m-%d %H:%M:%S"

#backup_regex = ".*{0}_(.*).zip"
backup_info_timestamp = "Timestamp - "
backup_info_file = "backup-info.txt"
timestamp_regex = f"{backup_info_timestamp}(.*)"

argumentList = sys.argv[1:]
verbose = False
dryRun = False

options = "c:v:d"
long_options = ["config", "verbose","dry","default"]

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
        elif currentArgument in ("-d", "--dry"):
            dryRun = True
            print("Dry run")
        elif currentArgument in ("--default"):
            config_path = None
            print("Using environment for config. Will not load or create config file.")
            
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

if config_path != None:
    Config.load_config(config_path);

test_path(Config.BACKUP_LOCATION)
test_path(Config.WORLD_LOCATION)

def log(str):
    if (verbose and not dryRun):
        mcr.command("say " + str)
    print(str)

def command(str):
    if (dryRun):
        return
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
    zip_name = f"backup_{tag}.zip"
    zip_path = os.path.join(Config.BACKUP_LOCATION, zip_name)
    global backup_zip
    if (backup_zip is None):
        backup_zip = zip_path
        print(f"Creating new zip {backup_zip}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_handle:
            zipDir(os.path.join(Config.WORLD_LOCATION,"world"), zip_handle)
            zipDir(os.path.join(Config.WORLD_LOCATION,"world_nether"), zip_handle)
            zipDir(os.path.join(Config.WORLD_LOCATION,"world_the_end"), zip_handle)
            write_backup_info(zip_handle)
    else:
        print(f"Copying from existing backup {backup_zip} to {zip_name}")
        shutil.copyfile(backup_zip,zip_path)
        
    log("Backup saved: " + zip_name)

def write_backup_info(zip_handle: zipfile.ZipFile):
    backupText = f"{backup_info_timestamp}{timestr}"
    zip_handle.writestr(backup_info_file, backupText)

def try_backup(tag: str, rate: timedelta):
    for root, dirs, files in os.walk(Config.BACKUP_LOCATION):
        for file in files:
            if (tag not in file):
                continue
            
            with zipfile.ZipFile(os.path.join(root,file), 'r') as archive:
                data = archive.read(backup_info_file).decode('UTF-8')
                match = re.search(timestamp_regex, data)
                if (not match):
                    continue
                
                backup_time = datetime.strptime(match.group(1), time_format)
                time_delta = now - rate
                if (time_delta <= backup_time):
                    print(f"Backup tag: {tag} within given rate. Skipping.")
                    return;
    backup(tag)

now = datetime.now()
timestr = datetime.strftime(now, time_format)

def run_backups() :
    try:
        for rate in Config.BACKUP_FREQUENCY:
            delta = time_deltas.get(rate)
            if (delta is None):
                print(f"Tag: {rate} is not a valid time rate. Tag must be one of the following: f{list(time_deltas)}")
                continue
            try_backup(rate, delta)
    except getopt.error as err:
        print (str(err))

log(f"Saving Backups: {timestr}")
if not dryRun:
    with MCRcon(Config.RCON_HOST, Config.RCON_PASSWORD, port=Config.RCON_PORT) as mcr:
        command("save-on")
        command("save-all")
        time.sleep(5);
        command("save-off")
        run_backups()
        command("save-on")
else:
    run_backups()
log("Backups complete")