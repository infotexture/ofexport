# My Usage Examples

The examples below can be run from a script such as `./ofexport-all.sh`
(see also `../documentation/examples.md`)

# AUTOEXPORT: Just the remaining projects and tasks (pruned, EXCLUDING done)

    ofexport -T taskpaper-lite-done -o ~/Desktop/OmniFocus-tasks_remaining.todo -a prune -E -a done=any

# Completed projects and tasks (pruned, ONLY done)

    ofexport -T taskpaper-lite-done -o ~/Desktop/OmniFocus-tasks_DONE.todo -a prune -a done=any

# Any projects and tasks that were done today

    ofexport -T taskpaper-lite-done -o ~/Desktop/OmniFocus-tasks_done-today.todo -a prune -a done='today'

# Any projects and tasks that were done last week

## TaskPaper

    ofexport -T taskpaper-lite-done -o ~/Desktop/OmniFocus-tasks_done-last-week.todo -a prune -a "done='last week'"

## Markdown

    ofexport -o ~/Desktop/OmniFocus-tasks_done-last-week.md -a prune -a "done='last week'"

# Set up new Markdown template to remove @done tags from "completed" report

    ofexport -T markdown-lite -o ~/Desktop/OmniFocus-tasks_done-last-week.md -a prune -a "done='last week'"


# VPI 

## Tasks from the VPI folder that were completed last week

    ofexport -T taskpaper-lite -f=VPI -a "completed='last week'" -o ~/Desktop/VPI-report_last-week.taskpaper --open

## VPI Markdown report for last week (flattened & pruned)

    ofexport -T markdown-lite -f=VPI -o ~/Desktop/VPI-report_last-week.md -a flatten -a prune -a "done='last week'"

## AUTOEXPORT: Remaining TMM tasks – replaces former `TMM.todo` 
(Removes @context & @project info, but keeps notes)

    ofexport -T taskpaper-lite-notes -p=TMM -o ~/Desktop/TMM_notes.todo -a prune -E -a done=any


# Adyton

## AUTOEXPORT: Remaining Adyton tasks – replaces former `Adyton.todo` 

    ofexport -T taskpaper-lite-notes -p=Adyton -o ~/Desktop/Adyton.todo -a prune -E -a done=any


# Default Examples

This produces the report of all uncompleted tasks that are flagged or due soon:

    ofexport -E -a done=any -I -t "flagged or (due='to tomorrow')" -o /tmp/ex8-due-or-flagged.taskpaper 
