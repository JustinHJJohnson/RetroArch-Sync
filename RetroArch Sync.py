import ftplib
from os import utime, path
from shutil import copy2
from datetime import datetime
from colorama import Fore, Style
from pathlib import Path

class Save:
    """
    Store some information about a save, used for sorting
    
    Keyword arguments:
        device: name of the device the save came from.\n
        lastModified: when the file was last editted, stored as time since epoch.\n
    """
    device: str
    lastModified: float

    def __init__(self, device: str, lastModified: float):
        self.device = device
        self.lastModified = lastModified

    def __repr__(self):
        return f"{self.device} ~ {self.lastModified}"

class Server:
    """
    Store the information about a device and it's FTP server.

    Keyword arguments:
        name: name of the device.\n
        hostname: the hostname or IP to connect to.\n
        port: the port to attempt an FTP connection on.\n
        path: the path to the save directory on the device.\n
        username: username for authentication, defaults to None.\n
        password: password for authentication, defaults to None.\n
    """
    name: str
    hostname: str
    port: int
    path: str
    username: str
    password: str
    connection: ftplib.FTP

    def __init__(self, name: str, hostname: str, port: int, path: str, username: str=None, password: str=None):
        self.name = name
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.connection = None

def error(string: str):
    """Print a string with a red background"""
    print(Fore.RED + string + Style.RESET_ALL)

def deleteFolder(path: Path):
    """Delete a non-empty folder"""
    for file in path.iterdir():
        fileToDelete = path / file
        if fileToDelete.is_dir():
            deleteFolder(fileToDelete)
        else:
            fileToDelete.unlink()
    path.rmdir()

def ftpConnect(ftp: ftplib.FTP, server: Server) -> bool:
    """Connect to a ftp server"""
    try: 
        ftp.connect(server.hostname, server.port)
    except:
        error(f"~~~~~~~~ Failed to connect to {server.name} ~~~~~~~~")
        error("Check that the device is running and that the IP and port are correct\n")
        return False
    # If the connection was successful, fetch the save files from the device's server
    if (server.username):
        try:
            ftp.login(server.username, server.password)
        except:
            error(f"~~~~~~~~ Failed to connect to {server.name} ~~~~~~~~")
            error("Invalid username or password")
            return False
    else:
        ftp.login()
    print(f"~~~~~~~~ Connected to {server.name} ~~~~~~~~")
    return True

# All the devices to syncronise
devices = [
    Server(
        "Switch",
        "192.168.0.54",
        5000,
        "retroarch/cores/savefiles/",
        "justinj0",
        "Qywter101"
    ),
    Server(
        "Phone",
        "192.168.0.53",
        12345,
        "RetroArch/savefiles/"
    )
]

# A set of unique saves
saves = set()
# Location for the most recent saves
saveFolder = Path("E:/Documents/Personal Projects/RetroArch Sync/Saves")
# Location to store a backup of all the saves on each device
backupFolder = Path("E:/Documents/Personal Projects/RetroArch Sync/Backups")
# The number of backups to keep
numBackups = 10
# How long to wait for a connection to be established
timeout = 10

# Create the folders to store saves if they doesn't already exist
if not saveFolder.is_dir():
    saveFolder.mkdir(parents=True)
if not backupFolder.is_dir():
    backupFolder.mkdir(parents=True)

# Check if there is more that the specified number of backups, delete if too many
backups = list(backupFolder.iterdir())
while len(backups) >= numBackups:
   deleteFolder(backupFolder / backups[0])
   backups = list(backupFolder.iterdir())

# Make new backup folder with current timestamp to organise
backupFolder /= datetime.now().strftime(r'%Y.%m.%d %H-%M-%S')
backupFolder.mkdir(parents=True)

# Loop through each device and try to connect to their FTP server to download the saves
print("~~~~~~~~ Downloading saves ~~~~~~~~")
for server in devices:
    print(f"\n~~~~~~~~ Connecting to {server.name} ~~~~~~~~")
    ftp = ftplib.FTP(timeout=timeout)
    if (ftpConnect(ftp, server)):
        try:
            ftp.cwd(server.path)
        except ftplib.error_perm:
            error(f"Could not move to {server.path}, check path and type of slash used")
            continue
        # Create a folder at the save location for this device's saves
        (backupFolder / server.name).mkdir(parents=True)
        # Fetch the files modified times
        # https://stackoverflow.com/questions/29026709/how-to-get-ftp-files-modify-time-using-python-ftplib
        files = ftp.mlsd()
        for file in files:
            name = file[0]
            # Hack for the switch ftpd as it returns the folder path as the first file for some reason
            if name[1:] in server.path : continue
            saves.add(name)
            # Remove .000 from the end of some systems modify time, notably the switch ftpd app/service   
            timestamp = file[1]['modify'].split(".")
            time = datetime.strptime(timestamp[0], r"%Y%m%d%H%M%S")
            # Download the file
            downloadLocation = backupFolder / server.name / name
            ftp.retrbinary(f"RETR {name}", open(downloadLocation, 'wb').write)
            # Set the modified time to be the same as the server
            utime(downloadLocation, (time.timestamp(), time.timestamp()))
            print(f"Downloaded {name} ~ {time}")
        #ftp.close()
        # Store to connection in the server object to save a reconnect later
        server.connection = ftp

# Create folder to store backup of the latest saves
(backupFolder / 'Latest Saves').mkdir()
# Go through each save and see which is newest based on the last time the file was modified
for save in saves:
    currentSaves = []
    for device in devices:
        if ((backupFolder/device.name/save).is_file()):
            currentSaves.append(
                Save(
                    device.name,
                    #os.path.getmtime(f"{backupFolder}\\{device.name}\\{save}")
                    path.getmtime(Path(f"{backupFolder}/{device.name}/{save}"))
                )
            )
    # Sort list based on modified time
    currentSaves.sort(key=lambda x: x.lastModified, reverse=True)
    print(f"{save} {currentSaves}")
    filePath = backupFolder / currentSaves[0].device / save
    # Copy files to the save folder and the latest saves backup folder
    copy2(filePath, saveFolder)
    copy2(filePath, backupFolder / 'Latest Saves')
    
print("\n\n~~~~~~~~ Uploading saves back to devices ~~~~~~~~")
# Upload the latest saves to the devices
for server in devices:
    print(f"\n~~~~~~~~ Uploading to {server.name} ~~~~~~~~")
    ftp = server.connection
    for save in saveFolder.iterdir():
        saveLocation = saveFolder / save.name
        # Upload the save to the device
        ftp.storbinary(f"STOR {save.name}", open(saveLocation, "rb"))
    ftp.close