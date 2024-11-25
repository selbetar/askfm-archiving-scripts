# askfm archiving scripts
This repository contains python scripts to backup an askfm user profile.
All publicly avaliable data will be saved into a sqlite3 database, and all pictures/videos will be downloaded to the output directory. The archival script uses askfm API instead of web scraping to save user data, which means it will be faster and can save threads/chats as well.

# Setup
1. Get [Python3](https://www.python.org/downloads/)
2. Create virtual environment
```sh
python3 -m venv venv
source .venv/bin/activate
python3 install -r requirements.txt
```

# Usage: Archiving

1. Open `config.py` and provide fill in the username, password, and the api key
2. Execute the python script `extractor.py`
```sh
python3 extractor.py usernames [usernames ...]

archive ask.fm profiles

positional arguments:
  usernames
```

Example
The following example archives the content of the profile called `askfm`
```sh
python3 extractor.py askfm
```
