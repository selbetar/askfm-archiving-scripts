# askfm archiving scripts
This repository contains python scripts that can be used to back askfm user profiles and generate html files from the archived data. All data is saved to a local sqlite3 database named `askfm.db`.


## askfm-archiving-scripts vs askfmArchiver
This tool utilizes the undocumented ASKfm API that is used in the mobile app, which means this tool can extract information that are only available on the mobile app such as chats/threads.

Unlike the web scraping tool, you will need to provide valid askfm credentials to be able to use it. The credentials are only sent to `ask.fm` as part of the request to their API.


# Setup
Note: the scripts/tools in this repository have been tested on Linux only, but they will probably work fine on other operating systems.

## Linux Setup
1. Install Python3.11
2. Clone the repository or download the [latest release](https://github.com/selbetar/askfm-archiving-scripts/releases/latest)
3. Execute setup.sh
```sh
./setup.sh
```
This will initialize the virtual environment and will install the required dependencies.


## Windows Setup
1. Download [Python3.11](https://www.python.org/downloads/release/python-3119/)
    - You can find the installer at the bottom of the page
    - Make sure to select `Add python to PATH`
2. Download the [Source code (zip)](https://github.com/selbetar/askfm-archiving-scripts/releases/latest) of the latest release
3. Unzip the downloaded file
4. Open `Powershell` and cd into the directory and execute `setup.ps1`

Example
```ps1
# change directory to the tool's folder
cd C:\askfm-archiving-scripts-1.0.0

# execute setup script
.\setup.ps1
```
If you get an error about the execution policy, you can change the policy by opening Powershell as administrator and executing the following
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned
```


# Usage: Archiving

1. Open `config.py` and fill in the username, password, and the api key which you can get from [here](https://justpaste.it/ls/i5ki7/q1nzc3mfn1yz2gue)
2. Execute the python script `extractor.py`

### Linux
```sh
./askfm-archiver.sh usernames [usernames ...]
```

### Windows
```powershell
.\askfm-archiver.ps1 usernames [usernames ...]
```

### Example
The following example archives the content of the profiles `test1 test2`
```sh
./askfm-archiver.sh test1 test2
```

```powershell
.\askfm-archiver.ps1 test1 test2
```

# Usage: HTML
You can generate html files of an archived user using the following command:

### Linux
```sh
./askfm-html.sh usernames [usernames ...]
```

### Windows
```powershell
.\askfm-html.ps1 usernames [usernames ...]
```

# Related work / See also
- The library utilized by the archiving tool: https://github.com/AskfmForHumans/askfm-api
