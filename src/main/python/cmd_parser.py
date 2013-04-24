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

import re
from treemodel import TASK, PROJECT, CONTEXT, FOLDER
from datetime import datetime
from datematch import process_date_specifier, match_date_against_range, date_range_to_str
import logging
import sys
from visitors import Filter

logging.basicConfig(format='%(asctime)-15s %(levelname)s %(message)s', stream=sys.stdout)
LOGGER = logging.getLogger('cmd_parser')
LOGGER.setLevel(level=logging.INFO)

# Primary/Real name is first
NAME_ALIASES = ['name', 'title', 'text', 'name']
START_ALIASES = ['date_to_start', 'start', 'started', 'begin', 'began']
COMPLETED_ALIASES = ['date_completed', 'done', 'end', 'ended', 'complete', 'completed', 'finish', 'finished', 'completion']
DUE_ALIASES = ['date_due', 'due', 'deadline']
FLAGGED_ALIASES = ['flagged', 'flag']
TYPE_ALIASES = ['type']

FLATTEN_ALIASES = ['flat', 'flatten']

def build_alias_lookups (): 
    mk_map = lambda x: {alias:x[0] for alias in x}
    result = {}
    result.update (mk_map (NAME_ALIASES))
    result.update (mk_map (START_ALIASES))
    result.update (mk_map (COMPLETED_ALIASES))
    result.update (mk_map (DUE_ALIASES))
    result.update (mk_map (FLAGGED_ALIASES))
    result.update (mk_map (TYPE_ALIASES))
    return result
    
ALIAS_LOOKUPS = build_alias_lookups ()
    
TOKEN_PATTERNS = [
          # tok name, pattern, text equivalent
          ('SP', ' ', ' '),
          ('TXT', '\\\\"', '"'),
          ('TXT', "\\\\'", "'"),
          ('TXT', "\\='", "="),
          ('OB', '\(', '('),
          ('CB', '\)', ')'),
          ('OSB', '\[', '['),
          ('CSB', '\]', ']'),
          ('NE', '!=', '!='),
          ('EQ', '=', '='),
          ('DQ', '"', '"'),
          ('AND', 'and', 'and'),
          ('OR', 'or', 'or'),
          ('NOT', '!', '!'),
          ('BS', '\\\\', '\\')
          ]

def sub_tokenise (tokens, tok_name, pattern, equiv):
    result = []
    for typ, val in tokens:
        if typ == 'UNK':
            pieces = re.split (pattern, val)
            if len (pieces) > 1:
                result.append ((typ, pieces[0]))
                pieces = pieces [1:]
                for piece in pieces:
                    result.append ((tok_name, equiv))
                    result.append ((typ, piece))
            else:
                result.append ((typ, val))
        else:
            result.append ((typ, val))
    return result
        
def tokenise (cmd):
    tokens = [('UNK',cmd)]
    for tok_name, pattern, equiv in TOKEN_PATTERNS:
        tokens = sub_tokenise (tokens, tok_name, pattern, equiv)
    result = []
    # Anything we haven't recognised is text
    for t,v in tokens:
        if t == 'UNK':
            if v != '':
                result.append(('TXT', v))
        else:
            result.append ((t, v))
    return result

def consume_whitespace (tokens):
    while len(tokens) > 0:
        t = tokens[0][0]
        if t != 'SP':
            return tokens
        else:
            tokens = tokens[1:]
    return []

def next_token (tokens, options):
    if len(tokens) == 0:
        assert False, 'end of tokens, expected ' + str(options)
    t,v = tokens[0]
    if not t in options:
        assert False, 'found "' + v + '" not: ' + str(options)
    return (t,v), tokens[1:]
    
def parse_string (tokens, stop_tokens):
    tokens = consume_whitespace (tokens)
    buf = []
    while len(tokens) > 0:
        t,v = tokens[0]
        tokens = tokens[1:]
        if t in stop_tokens:
            return unicode(''.join(buf)), [(t,v)] + tokens
        else:
            buf.append(v)
    return unicode(''.join(buf)), []

def and_fn (lhs, rhs):
    LOGGER.debug ('eval and: (%s) AND (%s)', lhs, rhs)
    assert type(lhs) == type(rhs), 'type error: ' + str (type(lhs)) + '!=' + str(type(rhs))
    assert type(lhs) == bool
    result = lhs and rhs
    LOGGER.debug ('result and: (%s)', result)
    return result

def or_fn (lhs, rhs):
    LOGGER.debug ('eval or: (%s) OR (%s)', lhs, rhs)
    assert type(lhs) == type(rhs), 'type error'
    assert type(lhs) == bool
    result = lhs or rhs
    LOGGER.debug ('result or: (%s)', result)
    return result

def eq_fn (lhs, rhs, lhs_is_field):
    if type (lhs) == datetime and type (rhs) == tuple:
        LOGGER.debug ('eval =: (%s) = (%s)', lhs, date_range_to_str(rhs))
        result = match_date_against_range (lhs, rhs)
    elif type (lhs) == tuple and type (rhs) == datetime:
        LOGGER.debug ('eval =:  (%s) = (%s)', date_range_to_str(lhs), rhs)
        result = match_date_against_range (rhs, lhs)
    elif type (lhs) == unicode and type (rhs) == unicode:
        if lhs_is_field:
            LOGGER.debug ('eval =: (%s) matches (%s)', lhs, rhs)
            result = re.search(rhs, lhs) != None
        else:
            LOGGER.debug ('eval =: (%s) = (%s)', lhs, rhs)
            result = lhs == rhs
    elif type(lhs) == bool and type (rhs) == bool:
        LOGGER.debug ('eval =: (%s) = (%s)', lhs, rhs)
        result = lhs == rhs
    else:
        assert False, 'unknown or incompatible types: ' + str(type(lhs)) + ' and ' + str(type(rhs))
    LOGGER.debug ('result =: (%s)', result)
    return result

def ne_fn (lhs, rhs, lhs_is_field):
    LOGGER.debug ('eval !=: (%s) != (%s)', lhs, rhs)
    result = not eq_fn (lhs, rhs, lhs_is_field)
    LOGGER.debug ('result !=: (%s)', result)
    return result

def adapt (x):
    if type (x) == str:
        return unicode (x)
    return x

def access_field (x, field):
    result = x.__dict__[field]
    result = adapt (result)
    LOGGER.debug ('accessing field %s %s: %s', str(type(result)), field, result)
    return adapt (result)

def parse_expr (tokens, now = datetime.now(), level = 0):
    tokens = consume_whitespace (tokens)
    (t,v), tokens = next_token (tokens, ['TXT', 'NOT', 'OB', 'OSB', 'DQ'])
    
    # NOT
    if t == "NOT":
        LOGGER.debug ('parse %s %s', level, t)
        expr, tokens = parse_expr (tokens, now=now, level=level+1)
        LOGGER.debug ('parse %s returned', level)
        return (lambda x: not expr (x)), tokens
    
    # LHS
    lhs_is_field = False
    LOGGER.debug ('parse %s looking for lhs', level)
    if t == 'TXT' and v =='true':
        LOGGER.debug ('parse %s literal %s', level, t)
        lhs = lambda x: True
    elif t == 'TXT' and v =='false':
        LOGGER.debug ('parse %s literal %s', level, t)
        lhs = lambda x: False
    elif t == 'TXT' and v in ALIAS_LOOKUPS:
        LOGGER.debug ('parse %s field %s', level, v)
        field = ALIAS_LOOKUPS[v]
        lhs = lambda x: access_field(x, field)
        lhs_is_field = True
    elif t == 'OB':
        LOGGER.debug ('parse %s start sub expr', level)
        lhs, tokens = parse_expr (tokens, now=now, level=level+1)
        LOGGER.debug ('parse %s returned', level)
        tokens = consume_whitespace (tokens)
        tokens = next_token (tokens, ['CB'])[1]
        LOGGER.debug ('parse %s end sub expr', level)
    elif t == 'DQ':
        string, tokens = parse_string (tokens, 'DQ')
        LOGGER.debug ('parse %s quoted string: %s', level, string)
        lhs = lambda x: string
        tokens = next_token (tokens, ['DQ'])[1]
    elif t == 'OSB':
        datespec, tokens = parse_string (tokens, 'CSB')
        rng = process_date_specifier (now, datespec)
        LOGGER.debug ('parse %s date spec: %s', level, date_range_to_str(rng))
        lhs = lambda x: rng
        tokens = next_token (tokens, ['CSB'])[1]
    else:
        assert False, "in expression found unexpected symbol: " + t + ':"' + v + '"'
    
    # OPERATOR 
    LOGGER.debug ('parse %s looking for operator', level)
    tokens = consume_whitespace (tokens)
    if len(tokens) == 0:
        LOGGER.debug ('parse %s done - no more tokens', level)
        return lhs, tokens
    
    
    (op,v), tokens = next_token (tokens,['AND', 'OR', 'EQ', 'NE', 'CB'])
    if op == 'CB':
        LOGGER.debug ('parse %s done - hit end brace', level)
        return lhs, [(op,v)] + tokens
    
    LOGGER.debug ('parse %s operator: %s', level, op)
    
    LOGGER.debug ('parse %s looking for rhs', level)
    rhs, tokens = parse_expr (tokens, now=now, level=level+1)
    LOGGER.debug ('parse %s returned', level)
    
    LOGGER.debug ('parse %s building lambda %s', level, op)
    if op == 'AND':
        return (lambda x: and_fn(lhs (x), rhs (x))), tokens
    elif op == 'OR':
        return (lambda x: or_fn(lhs (x), rhs (x))), tokens
    elif op == 'EQ':
        return (lambda x: eq_fn (lhs (x), rhs (x), lhs_is_field)), tokens
    elif op == 'NE':
        return (lambda x: ne_fn (lhs (x), rhs (x), lhs_is_field)), tokens

def log (x):
    #LOGGER.info ('------- analysing %s %s %s', x.id, x.type, x.name)
    return x

def log2 (x):
    #LOGGER.info ('------- result %s', x)
    return x
    
def make_filter (expr_str):
    LOGGER.info ('filter %s', expr_str)
    
    match_fn, tokens_left = parse_expr (tokenise (expr_str))
    match_fn_2 = lambda x,y: log2(match_fn (log(x)))
    return Filter ([TASK, PROJECT, CONTEXT, FOLDER], match_fn_2, "zzz", True, "kaplooey")
    '''
    bits = re.split (' ', expr_str, maxsplit=1)
    direction = bits[0].strip ()
    expr_str = ' '.join(bits[1:])
    
    match_fn, tokens_left = parse_expr (tokenise (bits[1]))
    if len (tokens_left) > 0:
        assert False, 'don\'t know what to do with: ' + str (tokens_left)
    match_fn_2 = lambda x,y: log2(match_fn (log(x)))

    if direction == '+':
        LOGGER.info ('filter i "%s" "%s"', direction, expr_str)
        return Filter ([TASK, PROJECT, CONTEXT, FOLDER], match_fn_2, "zzz", True, "kaplooey")
    else:
        LOGGER.info ('filter e "%s" "%s"', direction, expr_str)
        return Filter ([TASK, PROJECT, CONTEXT, FOLDER], match_fn_2, "zzz", False, "kaplooey")
    '''
            
