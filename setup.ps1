py -m venv venv

invoke-expression -Command  $PSScriptRoot/venv/Scripts/Activate.ps1

py -m pip install --upgrade pip
py -m pip install -r requirements.txt
