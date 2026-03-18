#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
alembic upgrade head
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8088 > /tmp/drivecheck-app.log 2>&1 &
sleep 1
open "http://127.0.0.1:8088/"
echo "DriveCheck started. Log: /tmp/drivecheck-app.log"
