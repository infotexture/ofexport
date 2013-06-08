'''
Copyright 2013 Paul Sidnell

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

from treemodel import PROJECT, Project, Node, Task, Context, Folder, Note, sort
import sqlite3
from os import environ, path
from datetime import datetime
from typeof import TypeOf
from xml.dom.minidom import parseString
import logging

logger = logging.getLogger(__name__)

'''
A library for loading a data model from the Omnifocus SQLite database.

---------
Notes on discovering what the Omni schema looks like

sqlite3 ~/Library/Caches/com.omnigroup.OmniFocus/OmniFocusDatabase2

.tables
Attachment   Folder       Perspective  Setting    
Context      ODOMetadata  ProjectInfo  Task       

sqlite> .schema Task
CREATE TABLE Task (persistentIdentifier text NOT NULL PRIMARY KEY, blocked integer NOT NULL, blockedByFutureStartDate integer NOT NULL, 
childrenCount integer NOT NULL, childrenCountAvailable integer NOT NULL, childrenCountCompleted integer NOT NULL, completeWhenChildrenComplete integer NOT NULL,
containingProjectContainsSingletons integer NOT NULL, containingProjectInfo text, containsNextTask integer NOT NULL, context text, creationOrdinal integer,
dateAdded timestamp NOT NULL, dateCompleted timestamp, dateDue timestamp, dateModified timestamp NOT NULL, dateToStart timestamp, effectiveContainingProjectInfoActive integer NOT NULL,
effectiveContainingProjectInfoRemaining integer NOT NULL, effectiveDateDue timestamp, effectiveDateToStart timestamp, effectiveFlagged integer NOT NULL,
effectiveInInbox integer NOT NULL, estimatedMinutes integer, flagged integer NOT NULL, hasCompletedDescendant integer NOT NULL, hasFlaggedTaskInTree integer NOT NULL,
hasUnestimatedLeafTaskInTree integer NOT NULL, inInbox integer NOT NULL, isDueSoon integer NOT NULL, isOverdue integer NOT NULL, maximumEstimateInTree integer,
minimumEstimateInTree integer, name text, nextTaskOfProjectInfo text, noteXMLData blob, parent text, projectInfo text, rank integer NOT NULL, repetitionMethodString text,
repetitionRuleString text, sequential integer NOT NULL);
CREATE INDEX Task_containingProjectInfo on Task (containingProjectInfo);
CREATE INDEX Task_context on Task (context);
CREATE INDEX Task_nextTaskOfProjectInfo on Task (nextTaskOfProjectInfo);
CREATE INDEX Task_parent on Task (parent);
CREATE INDEX Task_projectInfo on Task (projectInfo);

.schema ProjectInfo
CREATE TABLE ProjectInfo (pk text NOT NULL PRIMARY KEY, containsSingletonActions integer NOT NULL, folder text, folderEffectiveActive integer NOT NULL,
lastReviewDate timestamp, minimumDueDate timestamp, nextReviewDate timestamp, nextTask text, numberOfAvailableTasks integer NOT NULL, numberOfDueSoonTasks integer NOT NULL,
numberOfOverdueTasks integer NOT NULL, numberOfRemainingTasks integer NOT NULL, reviewRepetitionString text, status text NOT NULL, task text, taskBlocked integer NOT NULL,
taskBlockedByFutureStartDate integer NOT NULL, taskDateToStart timestamp);
CREATE INDEX ProjectInfo_folder on ProjectInfo (folder);
CREATE INDEX ProjectInfo_nextTask on ProjectInfo (nextTask);
CREATE INDEX ProjectInfo_task on ProjectInfo (task);


sqlite> .schema Folder
CREATE TABLE Folder (persistentIdentifier text NOT NULL PRIMARY KEY, active integer NOT NULL, childrenCount integer NOT NULL, creationOrdinal integer,
dateAdded timestamp NOT NULL, dateModified timestamp NOT NULL, effectiveActive integer NOT NULL, name text, noteXMLData blob, numberOfAvailableTasks integer NOT NULL,
numberOfDueSoonTasks integer NOT NULL, numberOfOverdueTasks integer NOT NULL, parent text, rank integer NOT NULL);
CREATE INDEX Folder_parent on Folder (parent);


.schema Context
CREATE TABLE Context (persistentIdentifier text NOT NULL PRIMARY KEY, active integer NOT NULL, allowsNextAction integer NOT NULL, altitude real,
availableTaskCount integer NOT NULL, childrenCount integer NOT NULL, creationOrdinal integer, dateAdded timestamp NOT NULL, dateModified timestamp NOT NULL,
effectiveActive integer NOT NULL, latitude real, localNumberOfDueSoonTasks integer NOT NULL, localNumberOfOverdueTasks integer NOT NULL, locationName text,
longitude real, name text, noteXMLData blob, notificationFlags integer, parent text, radius real, rank integer NOT NULL, remainingTaskCount integer NOT NULL,
totalNumberOfDueSoonTasks integer NOT NULL, totalNumberOfOverdueTasks integer NOT NULL);
CREATE INDEX Context_parent on Context (parent);

.schema Perspective (no name!!!)

CREATE TABLE Perspective (persistentIdentifier text NOT NULL PRIMARY KEY, creationOrdinal integer, dateAdded timestamp NOT NULL, dateModified timestamp NOT NULL, valueData blob);
'''

THIRTY_ONE_YEARS = 60 * 60 * 24 * 365 * 31 + 60 * 60 * 24 * 8

class OFNote (Note):
    def __init__ (self, item, noteXMLData):
        self.noteXMLData = noteXMLData
        self.item = item
        self.text = None
        self.lines = None
    def get_note_lines (self):
        if self.lines == None:
            # Currently getting this on demand because formatting it
            # for the whole DB is sloooooow
            logger.debug ('%s note: parsing xml', self.item.id)
            dom = parseString(self.noteXMLData)
            logger.debug ('%s note: collating lines', self.item.id)
            #print dom.toprettyxml ()
            self.lines = []
            for para in  dom.getElementsByTagName("p"):
                line = []
                for lit in  para.getElementsByTagName("lit"):
                    nodeValue = lit.firstChild.nodeValue
                    if nodeValue != None:
                        text = self.fix_dodgy_chars(nodeValue)
                        line.append(text)
                self.lines.append (u''.join(line))
            logger.debug ('%s note: processed', self.item.id)
        return self.lines
    def get_note (self):
        if self.text == None:
            self.text = '\n'.join (self.get_note_lines())
        return self.text
    def fix_dodgy_chars (self, text):
        try:
            return unicode (text)
        except:
            buf = []
            for c in text:
                try:
                    buf.append(unicode(c))
                except:
                    buf.append('?')
            return u''.join(buf)

def datetimeFromAttrib (ofattribs, name):
    val = ofattribs[name]
    if val == None:
        return None
    return datetime.fromtimestamp(THIRTY_ONE_YEARS + val)
    
class OFContext(Context):
    TABLE='context'
    COLUMNS=['persistentIdentifier', 'name', 'parent', 'childrenCount', 'rank', 'allowsNextAction']
    ofattribs = TypeOf ('ofattribs', dict)
    def __init__(self, ofattribs):
        Context.__init__(self,
                         name=ofattribs['name'])
        self.ofattribs = ofattribs
        self.order = ofattribs['rank']
        if 'persistentIdentifier' in ofattribs:
            self.id = ofattribs['persistentIdentifier']
            self.link = 'omnifocus:///context/' + ofattribs['persistentIdentifier']
        self.status = u'inactive' if 'allowsNextAction' in ofattribs and ofattribs['allowsNextAction'] == 0 else u'active'
        logger.debug ('loaded context: %s %s', self.id, self.name)

class OFTask(Task):
    TABLE='task'
    COLUMNS=['persistentIdentifier', 'name', 'inInbox', 'dateDue', 'dateCompleted','dateToStart', 'dateDue', 
             'projectInfo', 'context', 'containingProjectInfo', 'childrenCount', 'parent', 'rank',
             'flagged', 'noteXMLData']    
    ofattribs = TypeOf ('ofattribs', dict)
    def __init__(self, ofattribs):
        Task.__init__(self,
                      name=ofattribs['name'],
                      date_completed = datetimeFromAttrib (ofattribs,'dateCompleted'),
                      date_to_start = datetimeFromAttrib (ofattribs,'dateToStart'),
                      date_due = datetimeFromAttrib (ofattribs,'dateDue'),
                      flagged = bool (ofattribs['flagged']),
                      context=None)
        self.ofattribs = ofattribs
        self.order = ofattribs['rank']
        if 'persistentIdentifier' in ofattribs:
            self.id = ofattribs['persistentIdentifier']
            self.link = 'omnifocus:///task/' + ofattribs['persistentIdentifier']
        noteXMLData = ofattribs['noteXMLData']
        if noteXMLData != None:
            self.note = OFNote (self, noteXMLData)
        logger.debug ('loaded task: %s %s', self.id, self.name)
    
class OFFolder(Folder):
    TABLE='folder'
    COLUMNS=['persistentIdentifier', 'name', 'childrenCount', 'parent', 'rank', 'noteXMLData']
    ofattribs = TypeOf ('ofattribs', dict)
    def __init__(self, ofattribs):
        Folder.__init__(self,
                        name=ofattribs['name'])
        self.ofattribs = ofattribs
        self.order = ofattribs['rank']
        if 'persistentIdentifier' in ofattribs:
            self.id = ofattribs['persistentIdentifier']
            self.link = 'omnifocus:///folder/' + ofattribs['persistentIdentifier']
        logger.debug ('loaded folder: %s %s', self.id, self.name)
        
class ProjectInfo(Node):
    TABLE='projectinfo'
    COLUMNS=['pk', 'folder', 'status', 'nextTask']
    status = TypeOf ('status', unicode)
    nextTask = TypeOf ('nextTask', str)
    def __init__(self, ofattribs):
        Node.__init__(self,"ProjectInfo")
        self.ofattribs = ofattribs
        self.status = ofattribs['status']
        self.next_task = None if ofattribs['nextTask'] == None else str(ofattribs['nextTask'])

class OFProject(Project):
    ofattribs = TypeOf ('ofattribs', dict)
    folder = TypeOf ('folder', Folder)
    project_info = TypeOf ('project_info', ProjectInfo)
    def __init__(self):
        # UNUSUAL - don't call super constructor
        # We convert these from tasks rather than construct them
        pass

def query (conn, clazz):
    c = conn.cursor()
    columns = clazz.COLUMNS
    results = {}
    for row in c.execute('SELECT ' + (','.join(columns)) + ' from ' + clazz.TABLE):
        rowData = {}
        for i in range(0,len(columns)):
            key = columns[i]
            val = row[i]
            rowData[key] = val
        node = clazz (rowData)
        results[rowData[columns[0]]] = node
    c.close()
    return results

def transmute_projects (project_infos, tasks):
    '''
    Some tasks are actually projects, convert them
    '''
    logger.debug ('transmuting projects')
    projects = {}
    for project in tasks.values():        
        if project.ofattribs['projectInfo'] != None:
            logger.debug ('transmuting: %s %s', project.id, project.name)
            projects[project.ofattribs['persistentIdentifier']] = project
            project_info = project_infos[project.ofattribs['projectInfo']]
            project.__class__ = OFProject
            project.__init__()
            project_info.project = project
            project.type = PROJECT
            project.project_info = project_info
            project.status = project_info.status
    return projects

def wire_projects_and_folders (projects, folders, tasks):
    logger.debug ('wiring projects and folders')
    for project in projects.values():
        project_info = project.project_info
        if project.project_info != None:
            folder_ref = project_info.ofattribs['folder']
            if folder_ref != None:
                logger.debug ('wiring: %s %s', project.id, project.name)
                folder = folders[folder_ref]
                project.folder = folder
                folder.add_child (project)    
        if project_info.next_task != None:
            task = tasks[project_info.next_task]
            task.next = True

def wire_task_hierarchy (tasks):
    logger.debug ('wiring type hierarchy')
    for task in tasks.values():  
        if task.ofattribs['parent'] != None:
            logger.debug ('wiring: %s %s', task.id, task.name)
            parent = tasks[task.ofattribs['parent']]
            parent.add_child (task)
            
def wire_tasks_to_enclosing_projects (project_infos, tasks, inbox):
    logger.debug ('wiring tasks to enclosing projects')
    for task in tasks.values():  
        if task.ofattribs['containingProjectInfo'] != None:
            logger.debug ('wiring: %s %s', task.id, task.name)
            project_info = project_infos[task.ofattribs['containingProjectInfo']]
            project = project_info.project
            task.project = project
        elif task.ofattribs['inInbox']:
            inbox.add_child (task)
            
       
def wire_tasks_and_contexts (contexts, tasks, no_context):
    logger.debug ('wiring tasks and contexts')
    for task in tasks.values():
        logger.debug ('wiring: %s %s', task.id, task.name)
        if task.ofattribs['context'] != None:
            context = contexts[task.ofattribs['context']]
            task.context = context
            context.children.append(task)
        else:
            task.context = no_context
            no_context.children.append(task)
            
def wire_folder_hierarchy (folders):
    logger.debug ('wiring folder hierarchy')
    for folder in folders.values():
        if folder.ofattribs['parent'] != None:
            logger.debug ('wiring: %s %s', folder.id, folder.name)
            parent = folders[folder.ofattribs['parent']]
            parent.add_child (folder)
                
def wire_context_hierarchy (contexts):
    logger.debug ('wiring context hierarchy')
    for context in contexts.values():
        if context.ofattribs['parent'] != None:
            logger.debug ('wiring: %s %s', context.id, context.name)
            parent = contexts[context.ofattribs['parent']]
            parent.add_child (context)

def only_roots (items):
    roots = []
    for item in items:
        if item.parent == None:
            roots.append(item)
    return roots

def build_model (db):
    conn = sqlite3.connect(db)
    contexts = query (conn, clazz=OFContext)
    no_context = Context(name = 'No Context')
    inbox = Project (name='Inbox')
    project_infos = query (conn, clazz=ProjectInfo)
    folders = query (conn, clazz=OFFolder)
    tasks = query (conn, clazz=OFTask)
    
    projects = transmute_projects (project_infos, tasks)
    wire_projects_and_folders(projects, folders, tasks)
    wire_task_hierarchy(tasks)
    wire_tasks_to_enclosing_projects (project_infos, tasks, inbox)
    wire_tasks_and_contexts(contexts, tasks, no_context)
    wire_folder_hierarchy (folders)
    wire_context_hierarchy (contexts)
    
    conn.close ()
    
    # Find top level items
    project_roots = only_roots (projects.values())
    folder_roots = only_roots (folders.values())
    root_projects_and_folders = project_roots + folder_roots
    root_contexts = only_roots (contexts.values())
    root_contexts.insert(0, no_context)
    root_projects_and_folders.insert(0, inbox)
    sort(root_projects_and_folders)
    sort(root_contexts)
    
    root_folder = Folder (name='')
    for child in root_projects_and_folders:
        root_folder.add_child(child)
        
    root_context = Context (name='', status='active')
    for child in root_contexts:
        root_context.add_child(child)
        
    return root_folder, root_context
        
def find_database (databases):
    home = environ['HOME']
    databases = [home + x for x in databases]
    for db in databases:
        logger.debug ("testing for db %s", db)
        if (path.exists (db)):
            logger.info ("found db %s", db)
            return db
    raise IOError ('cannot find OmnifocusDatabase in ' + databases)
