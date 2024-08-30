#!/bin/sh
git push
ssh 44ed "cd debatron; git pull; sudo systemctl restart debatron"
