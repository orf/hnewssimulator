#!/usr/bin/env bash
python chains.py
python render.py
cp -r dist/ /var/www/hnews -f