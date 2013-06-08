#!/bin/bash

# Run this script (via Hazel or Launchd) whenever the OmniFocus database is updated

# Since `source ~/.bash_profile` doesn't work in Hazel or launchd, set PATH here

# 2013-05-17: Explicitly add OmniFocus `ofexport` tool to PATH
# See <https://github.com/psidnell/ofexport/blob/master/DOCUMENTATION.md>
export OFEXPORT_HOME="/Users/rofish/Documents/Setup/Scripts/OmniFocus/ofexport"
export PATH=$PATH:"$OFEXPORT_HOME/bin"

# Export the full content with all notes, tags, contexts, backlink URLs, etc.
ofexport -o ~/Documents/Dropbox/Notes/OmniFocus-truth.todo

# Export a simpler, less cluttered version with just the projects and tasks
ofexport -T taskpaper-lite-done -o ~/Documents/Dropbox/Notes/OmniFocus-tasks.todo

# Exit with status of last command.
exit $?
