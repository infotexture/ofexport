#!/bin/bash

# Run this script (via Hazel or Launchd) whenever the OmniFocus database is updated

# Since `source ~/.bash_profile` doesn't work in Hazel or launchd, set PATH here

# 2013-05-17: Explicitly add OmniFocus `ofexport` tool to PATH
# See <https://github.com/psidnell/ofexport/blob/master/DOCUMENTATION.md>
export OFEXPORT_HOME="/Users/rofish/Documents/Setup/Scripts/OmniFocus/ofexport"
export PATH=$PATH:"$OFEXPORT_HOME/bin"

# Export the full content with all notes, tags, contexts, backlink URLs, etc.
ofexport -o ~/Documents/Dropbox/Notes/OmniFocus-truth.todo

# Export just the remaining projects and tasks (pruned, EXCLUDING done)
ofexport -T taskpaper-lite-done -o ~/Documents/Dropbox/Notes/OmniFocus-tasks.todo -a prune -E -a done=any

# Remaining TMM tasks
ofexport -T taskpaper-lite-notes -p=TMM -o ~/Documents/Dropbox/Notes/TMM.todo -a prune -E -a done=any

# Remaining Adyton/Gateprotect tasks
ofexport -T taskpaper-lite-notes -p=Gateprotect -o ~/Documents/Dropbox/Notes/Gateprotect.todo -a prune -E -a done=any

# Remaining eBay / mobile.international tasks
ofexport -T taskpaper-lite-notes -p=eBay -o ~/Documents/Dropbox/Notes/eBay.todo -a prune -E -a done=any

# Remaining ipoque tasks
# ofexport -T taskpaper-lite-notes -p=ipoque -o ~/Documents/Dropbox/Notes/ipoque.todo -a prune -E -a done=any

# Remaining OD-OS tasks
# ofexport -T taskpaper-lite-notes -p=OD-OS -o ~/Documents/Dropbox/Notes/OD-OS.todo -a prune -E -a done=any

# Remaining Zeta/Wire tasks
ofexport -T taskpaper-lite-notes -p=Wire -o ~/Documents/Dropbox/Notes/Wire.todo -a prune -E -a done=any

# Exit with status of last command.
exit $?
