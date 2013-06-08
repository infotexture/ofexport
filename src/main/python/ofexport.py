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

import os
import codecs
import getopt
import sys
import json
from treemodel import traverse, Visitor, FOLDER, CONTEXT, PROJECT, TASK
from omnifocus import build_model, find_database
from datetime import date, datetime
from plugin_json import read_json
from help import print_help, SHORT_OPTS, LONG_OPTS
from fmt_template import FmtTemplate
from cmd_parser import make_filter
import logging
import cmd_parser
from visitors import Tasks

logging.basicConfig(format='%(asctime)-15s %(name)s %(levelname)s %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.ERROR)

LOGGER_NAMES = [
                __name__,
                'cmd_parser',
                'visitors',
                'datematch',
                'treemodel',
                'omnifocus',
                'fmt_template',
                'plugin_ics']

class SummaryVisitor (Visitor):
    def __init__ (self):
        self.counts = {}
    def end_any (self, item):
        if not 'counted' in item.attribs:
            item.attribs['counted'] = True
            if item.type in self.counts:
                self.counts[item.type] = self.counts[item.type] + 1
            else:
                self.counts[item.type] = 1
    def print_counts (self):
        # Subtract for the extra invisible roots that we've added.
        if CONTEXT in self.counts:
            self.counts[CONTEXT] = self.counts[CONTEXT]-1
        if FOLDER in self.counts:
            self.counts[FOLDER] = self.counts[FOLDER]-1
        
        logger.info ('Report Contents:')
        logger.info ('----------------')
        for k,v in [(k,self.counts[k]) for k in sorted(self.counts.keys())]:
            k = ' ' * (8 - len(k)) + k + 's:'
            logger.info (k + ' ' + str(v))
        logger.info ('----------------')

def load_config (home_dir):
    logger.info ('loading config')
    instream=codecs.open(home_dir + '/ofexport.json', 'r', 'utf-8')
    config = json.loads(instream.read())
    instream.close ()
    return config

def load_template (template_dir, name):
    logger.info ('loading template: %s', name)
    instream=codecs.open(template_dir + '/' + name + '.json', 'r', 'utf-8')
    template = FmtTemplate (json.loads(instream.read()))
    instream.close ()
    return template

def fix_abbrieviated_expr (typ, arg):
    if arg.startswith ('=') or arg.startswith ('!='):
        if typ == 'any' or typ == 'all':
            result = 'name' + arg + ''
        else:
            result = '(type=' + typ + ') and (name' + arg + ')'
    elif arg in ['prune', 'flatten']:
        result = arg + ' ' + typ
    elif arg.startswith ('sort'):
        if arg == 'sort':
            result = arg + ' ' + typ + ' text'
        else:
            bits = arg.split ()
            assert len (bits) == 2, 'sort can have one field type argument'
            result = 'sort' + ' ' + typ + ' ' + bits[1]
    else:
        if typ == 'any' or typ == 'all':
            result = arg
        else:
            result = '(type=' + typ + ') and (' + arg + ')'
    logger.debug ("adapted argument: '%s'", result)
    return result

def set_debug_opt (name, value):
    if name== 'now' : 
        the_time = datetime.strptime (value, "%Y-%m-%d")
        cmd_parser.the_time = the_time
 
if __name__ == "__main__":
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    today = date.today ()
    time_fmt='%Y-%m-%d'
    opn=False
    project_mode=True
    file_name = None
    infile = None
    home_dir = os.environ['OFEXPORT_HOME']
    template_dir = home_dir + '/templates'
    include = True
    
    type_config_override_data = {}
    
    config = load_config (home_dir)
    
    opts, args = getopt.optlist, args = getopt.getopt(sys.argv[1:],SHORT_OPTS, LONG_OPTS)
    
    assert len (args) == 0, "unexpected arguments: " + str (args)
        
    for opt, arg in opts:
        if '--open' == opt:
            opn = True
        elif '-o' == opt:
            file_name = arg
        elif '-i' == opt:
            infile = arg
        elif '-T' == opt:
            type_config_override_data['template'] = arg
        elif '-v' == opt:
            for logname in LOGGER_NAMES:
                logging.getLogger(logname).setLevel (logging.INFO)
        elif '-V' == opt:
            level = arg
            for logname in LOGGER_NAMES:
                logging.getLogger(logname).setLevel (logging.__dict__[arg])
        elif '-z' == opt:
            for logname in LOGGER_NAMES:
                logging.getLogger(logname).setLevel (logging.DEBUG)
        elif '--log' == opt:
            bits = arg.split('=')
            assert len(bits) == 2
            name = bits[0]
            level = bits[1]
            if name=='ofexport':
                name = __name__
            logging.getLogger(name).setLevel (logging.__dict__[level])
        elif '--debug' == opt:
            bits = arg.split('=')
            assert len(bits) == 2
            name = bits[0]
            value = bits[1]
            set_debug_opt (name, value)
        elif opt in ('-?', '-h', '--help'):
            print_help ()
            sys.exit()
    
    if file_name == None:
        # This blank suffix is mapped to a plugin/template in the config
        fmt = ''
    else:
        assert file_name.find ('.') != -1, "filename has no suffix"
        dot = file_name.index ('.')
        fmt = file_name[dot+1:]
    
    if infile != None:
        root_project, root_context = read_json (infile)
    else:    
        root_project, root_context = build_model (find_database (config['db_search_path']))
    
    subject = root_project
        
    for opt, arg in opts:
        logger.debug ("executing option %s : %s", opt, arg)
        visitor = None
        if opt in ('--project', '-p'):
            fixed_arg = fix_abbrieviated_expr(PROJECT, arg)
            visitor = make_filter (fixed_arg, include)
        elif opt in ('--task', '-t'):
            fixed_arg = fix_abbrieviated_expr(TASK, arg)
            visitor = make_filter (fixed_arg, include)
        elif opt in ('--context', '-c'):
            fixed_arg = fix_abbrieviated_expr(CONTEXT, arg)
            visitor = make_filter (fixed_arg, include)
        elif opt in ('--folder', '-f'):
            fixed_arg = fix_abbrieviated_expr(FOLDER, arg)
            visitor = make_filter (fixed_arg, include)
        elif opt in ('--any', '-a'):
            visitor = make_filter (fix_abbrieviated_expr('any', arg), include)
        elif opt in ('--tasks'):
            visitor = Tasks (root_project, root_context)
        elif '-C' == opt:
            logger.info ('context mode')
            project_mode = False
            subject = root_context
        elif '-P' == opt:
            logger.info ('project mode')
            project_mode = True
            subject = root_project
        elif '-I' == opt:
            logger.info ('include mode')
            include = True
        elif '-E' == opt:
            include = False
            logger.info ('exclude mode')
        
        logger.debug ("created filter %s", visitor)
        if visitor != None:
            logger.info ('running filter %s', visitor)
            traverse (visitor, subject, project_mode=project_mode)
            
    logger.info ('Generating: %s', file_name)
    
    if file_name != None:
        out=codecs.open(file_name, 'w', 'utf-8')
    else: 
        out = sys.stdout
    
    generated = False
    file_types = config['file_types']
    for type_config in file_types.values():
        if not generated and fmt in type_config['suffixes']:
            plugin = 'plugin_' + type_config['plugin']
            m = __import__(plugin)
            type_config.update (type_config_override_data)
            m.generate(out, root_project, root_context, project_mode, template_dir, type_config)
            generated = True
    
    if not generated:
        raise Exception ('unknown format ' + fmt)
    
    if file_name != None:
        out.close()
        if opn:
            os.system("open '" + file_name + "'")
        
    visitor = SummaryVisitor ()
    traverse (visitor, root_project, project_mode=True)
    traverse (visitor, root_context, project_mode=False)
    visitor.print_counts()
