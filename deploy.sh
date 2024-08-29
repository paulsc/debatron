#!/bin/sh
ssh 44ed "cd debatron; git pull; sudo systemctl restart debatron"
