#!/bin/bash

# Hazel runs this script whenever the OmniFocus database is updated

# Export the full content with all notes, tags, contexts, backlink URLs, etc.
ofexport -o ~/Documents/Dropbox/Notes/OmniFocus-truth.todo

# Export a simpler, less cluttered version with just the projects and tasks
ofexport -T taskpaper-lite -o ~/Documents/Dropbox/Notes/OmniFocus-tasks.todo
