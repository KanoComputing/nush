

        # NUSH 0.1 CORE NAMESPACE
        # This is Free Software (GPL)


import os
import cgi
import json
import shutil
from time import sleep

import cherrypy
import pipes

from subprocess import Popen, PIPE


# API OBJECT: shell
# =================

class Shell:

    '''Wraps the shell instance for the user's namespace.'''

    def send(self, data): radio.send('pin0', data)

    def evaluate(self, expression, extras=None):

        pin = issue_pin()
        jscript = 'supereval(pkg.pin, pkg.expression, pkg)'

        package = {'jscript': jscript, 'pin': pin, 'expression': expression}
        if extras: package.update(extras)
        self.send(json.dumps(package))

        while pin not in superspace: pass
        return superspace.pop(pin)

    def execute(self, jscript, extras=None):

        package = {'jscript': jscript}
        if extras: package.update(extras)
        self.send(json.dumps(package))

    def prompt(self, prompt='>>>'):

        return self.evaluate('prompt(pkg.prompt)', {'prompt': prompt})

    def create_feed(self, color, title, message, body=''):

        self.send(feed(color, title, message, body))

    def create_frame(self, color, title, message, path, height=16):

        height = height * 16
        height = str(height) + 'px'
        body = '<iframe src="{0}" scrolling=yes style="width: 100%; border: 1px solid #222; height: {1}"></iframe>'
        self.create_feed(color, title, message, body.format(path, height))

    def create_tab(self, url): self.execute('window.open("{0}")'.format(url))

    def clear(self): self.execute('clear_feeds()')

    def license(self):

        self.create_feed('green', 'free', 'GNU General Public License', license_info)
        self.execute('editor.focus()')



# INTERNAL: DOMAINS MANAGER
# =========================

class DomainsManager:

    def __init__(self): self.domains = {}

    def register(self, domain, seen=True):

        self.domains[domain.domain] = domain
        if seen: shell.execute('toastr.success("NEW DOMAIN: {0}")'.format(domain.domain))

    def read_post(self):

        try: return cherrypy.request.body.read().decode()
        except: return None

    def handle(self, *args, **kargs):

        args = list(args)
        data = self.read_post()

        domain = self.domains[args.pop(0)]
        method = args.pop(0)

        if data: return getattr(domain, method)(data, *args, **kargs)
        else: return getattr(domain, method)(*args, **kargs)

    handle.exposed = True



# INTERNAL: EMPTY DOMAIN FOR HANDLERS
# ===================================

class OrphanHandlers: domain = 'handlers'



# INTERNAL: BUILT IN DOMAIN HANDLERS
# ==================================

class CoreBuiltIns:

    domain = 'builtin'

    def issue_pin(self): return superpin()

    def superspace(self, data=None):

        if data: superspace.update(json.loads(data))
        return json.dumps(superspace)

    def editor(self, path):

        highlighting = {
            'py':   'python',
            'htm':  'html',
            'html': 'html',
            'css':  'css',
            'js':   'javascript',
            'json': 'json'
            }

        ext = path.split('.')[-1]
        try: lang = highlighting[ext]
        except: lang = ''

        appdir = ROOTDIR + '/static/apps/editor'
        with open(appdir + '/editor.html') as f: editor = f.read()

        return editor.replace(
            '$$ title $$', path.split('/')[-1]
            ).replace(
            '$$ appdir $$', appdir
            ).replace(
            '$$ filepath $$', path
            ).replace(
            '$$ lang $$', lang
            )

    def load_file(self, path, timestamp): return open(path)



# COMMAND: edit
# -------------

def edit(path=''):

    '''Command for opening a text file in a new editor tab.'''

    if not path: return shell.create_feed(
        'red', 'edit', 'the edit command can not be called without arguments'
        )

    tokens = path.split()

    if tokens[0] in ('-n', '-new'):

        if len(tokens) != 2:

            return shell.create_feed(
                'red', 'edit', 'you need to provide a path to the new file'
                )

        path = path_resolve(tokens[1])

        if os.path.isfile(path):

            return shell.create_feed(
                'red', 'edit', 'there\'s already a file at <span class=yellow>{0}</span>'.format(path)
                )

        try:

            with open(path, 'w') as f: f.write('')

        except IOError: return shell.create_feed(
            'red', 'edit', 'there\'s no path to <span class="yellow">{0}</span>'.format(path)
            )

    else:

        path = path_resolve(path)

        if not os.path.isfile(path):

            return shell.create_feed(
                'red', 'edit', 'there\'s no file at <span class="yellow">{0}</span>'.format(path)
                )

    return shell.execute("window.open('/nush/builtin/editor?path={0}')".format(path))



# COMMAND: goto
# -------------

def goto(path=''):

    '''Command for changing the current working directory.'''

    if not path:

        os.chdir(HOME)
        message = 'the working directory is now <span class="yellow">{0}</span>'.format(HOME)
        return shell.create_feed('green', 'goto', message)

    path = path_resolve(path)

    try: os.chdir(path)
    except OSError:

        message = 'there\'s no directory at <span class="yellow">{0}</span>'.format(path)
        return shell.create_feed('red', 'goto', message)

    body = dir2html(path)
    message = 'the working directory is now <span class="yellow">{0}</span><br><br>'.format(path)
    return shell.create_feed('green', 'goto', message, body)



# COMMAND: view
# -------------

def view(path=''):

    '''Command for viewing directories and files.'''

    if not path: path = os.getcwd()
    else: path = path_resolve(path)

    ends = path.endswith

    if os.path.isfile(path):

        if ends('.sh.py'): return launch_script(path)

        elif ends('.mp4') or ends('.ogg'):

            message = 'rendering the video at'
            file_ext = os.path.splitext(path)[1][1:]
            body = (
                '<video height="200" controls autoplay><source src="{0}"></video>'
                ).format(path, file_ext)

        elif ends('.mp3'):

            message = 'rendering the audio at'
            body = '<audio controls autoplay><source src="{0}" type="audio/mpeg"></audio>'.format(path)

        elif ends('.png') or ends('.jpg') or ends('.jpeg'):

            message = 'rendering the image at'
            body = '<img src="{0}">'.format(path)

        else:

            message = 'rendering the text file at'
            body = escape_html(open(path).read())

    elif os.path.isdir(path):

        message = 'rendering the directory at' if path else 'rendering the working directory, currently at'
        body = dir2html(path)

    else: return shell.create_feed(
        'red', 'view', 'there\'s nothing at <span class="yellow">{0}</span>'.format(path)
        )

    message = '{0} <span class="yellow">{1}</span>'.format(message, path)
    return shell.create_feed('green', 'view', message, body)



# COMMAND: mark
# -------------

def mark(args=''):

    '''Command for Managing Bookmarks.'''

    def update_bookmarks_file():

        with open(ROOTDIR+'/static/apps/shell/bookmarks.json', 'w') as f: f.write(json.dumps(BOOKMARKS))

    tokens = args.split()
    length = len(tokens)

    # show bookmarks and return...

    if not tokens:

        output = ''
        for key in BOOKMARKS.keys():

            output += (
                '<span class=pea>{0}</span><br><span class=yellow>{1}</span><br><br>'
                ).format(key, BOOKMARKS[key])

        if not output: return shell.create_feed('green', 'mark', 'there are no bookmarks to list')
        return shell.create_feed('green', 'mark', 'listing current bookmarks', output[:-8])

    # or delete a bookmark and return...

    if tokens[0] in ('-d', '-del', '-delete'):

        if length == 1: return shell.create_feed(
            'red', 'mark', 'you must name the bookmark you want deleting'
            )

        name = tokens[1]

        try:

            del BOOKMARKS[name]
            update_bookmarks_file()
            return shell.create_feed(
                'green', 'mark', 'deleted the bookmark <span class="yellow">{0}</span>'.format(name)
                )

        except KeyError: return shell.create_feed(
            'red', 'mark', 'there\'s no bookmark named <span class="yellow">{0}</span>'.format(name)
            )

    # or create a new bookmark...

    if length == 1: name, path = tokens[0], get_cwd()       # bookmark the current working directory
    else: name, path = tokens[1], path_resolve(tokens[0])   # bookmark the given path

    BOOKMARKS[name] = path
    update_bookmarks_file()
    message = (
        'a bookmark named <span class="yellow">{0}</span> now points to <span class="yellow">{1}</span>'
        ).format(name, path)

    return shell.create_feed('green', 'mark', message)


# COMMAND: move
# -------------

def move(args=''):
    
    tokens = args.split()
    
    if len(tokens) != 2: return shell.create_feed(
        'red', 'move', 'you must provide two paths: <span class=yellow>.move /from /to</span>'
        )
        
    item, destination = path_resolve(tokens[0]), path_resolve(tokens[1])
    
    if os.path.isdir(item): kind = 'directory'
    elif os.path.isfile(item): kind = 'file'
    else: return shell.create_feed('red', 'move', 'there\'s nothing at <span class=yellow>{0}</span>'.format(item))
    
    if not os.path.isdir(destination): return shell.create_feed(
        'red', 'move', 'there\'s no directory at <span class=yellow>{0}</span>'.format(destination)
        )
    
    shutil.move(item, destination)
    shell.create_feed(
        'green', 'mark',
        'moved the {0} at <span class=yellow>{1}</span> to <span class=yellow>{2}</span>'.format(kind, item, destination)
        )



# GLOBAL FUNCTIONS
# ----------------

def superpin():

    '''Function that increments and then returns the superpin as an id string.'''

    superspace['SUPERPIN'] += 1
    return 'pin' + str(superspace['SUPERPIN'])


def feed(color, title, message, body=''):

    '''Generate a new feed package with an optional body.'''

    if body: body = '<div class=padded_feed>{0}</div>'.format(body)

    feed = '''
        <span class="{0}">{1}</span> <span class=grey>#</span>
        <span style="float: right" onclick="this.parentNode.parentNode.removeChild(this.parentNode); editor.focus()">
        <span style="padding-right: 4px" class="dull kill_button hint--left hint--bounce"
            data-hint="Delete This Feed">x</span></span>
        {2}{3}'''.format(color, title, message, body)

    return json.dumps({'feed': feed, 'jscript': 'create_feed(pkg.feed)'})


def escape_html(html): return '<xmp>{0}</xmp>'.format(html)


def path_resolve(path):

    '''This function patches the way paths are printed, so they look consistant.'''

    if not path: return path
    path = path_expand(path)
    if path != '/' and path.endswith('/'): path = path[:-1]
    return path[1:] if path.startswith('//') else path


def path_expand(path):

    '''Expand paths, including bookmarks, to absolute paths.'''

    cwd = os.getcwd()
    dad = os.path.dirname(cwd)
    starts = path.startswith
    normalise = os.path.normpath

    if   starts('/'):   return path
    elif starts('./'):  return normalise(cwd + path[1:])
    elif starts('../'): return normalise(dad + path[2:])
    elif starts('~/'):  return os.path.expanduser("~") + path[1:]
    elif starts('|'):

        try:

            if not '/' in path: return BOOKMARKS[path[1:]]

            name = path[1:path.find('/')]
            tail = path[path.find('/'):]
            return BOOKMARKS[name] + tail

        except KeyError: return path

    else: return cwd + '/' + path


def dir2html(path):

    '''Render a directory's contents as HTML, as used by the view and goto command.'''

    dirs, files = '', ''
    items = os.listdir(path)
    items.sort()

    for item in items:

        ends = item.endswith
        full_path = '{0}/{1}'.format(path, item)

        if os.path.isdir(full_path):                                                                        # directories

            dirs += '''<span class="orange">{0}</span><br>'''.format(item)
            continue

        elif item.startswith('README') or item.startswith('LICENSE'): color = 'white'                       # specials
        elif ends('.py') or ends('.rb') or ends('.bsh') or ends('.lua'): color = 'yellow'                   # executables
        elif ends('.html') or ends('.md') or ends('.css') or ends('.js') or ends('.json'): color = 'cyan'   # web stuff
        elif ends('.png') or ends('.jpg') or ends('.jpeg') or ends('.mp4'): color = 'green'                 # media files
        elif ends('.zip'): color = 'pea'                                                                    # regular archives
        elif ends('.apk'): color = 'pink'                                                                   # android packages
        else: color = 'grey'                                                                                # everything else

        files += '''<span class="{0}">{1}</span><br>'''.format(color, item)

    return dirs + files if dirs or files else '<span class=dull>(this directory is empty)</span>'


def bosh(line):

    '''Get the output of a system command as a string.'''

    stdout, stderr = Popen([line], shell=True, stdout=PIPE, stderr=PIPE).communicate()
    output = stdout if stdout else stderr
    return(output.decode())



# GLOBAL NAMESPACE
# ================

def init():

    global issue_pin, domains, handlers

    issue_pin = superpin
    domains = DomainsManager()
    server.nush = domains.handle
    handlers = OrphanHandlers()
    domains.register(handlers, False)
    domains.register(CoreBuiltIns(), False)


# the current user's home directory
HOME = os.path.expanduser("~")

# get a path to this application's root directory
ROOTDIR = os.path.dirname(os.path.abspath(__file__))

# load the bookmarks.json file into a dict
BOOKMARKS = json.loads(open(ROOTDIR+'/static/apps/shell/bookmarks.json').read())

# this code is executed inside the interpreter when it's created
prime_namespace = '''
import os
nush.init()
from nush import ROOTDIR
from nush import escape_html, handlers, radio, domains
from nush import superspace, path_resolve, issue_pin, bosh
'''.format(ROOTDIR)


# this is used in the shell to display licensing information
license_info = '''
NUSH is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License <br>
as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. <br> <br>

NUSH is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty <br>
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. <br> <br>

A copy of the GNU General Public License is included with NUSH, and can be found in the root directory of the <br>
application, in a file named LICENSE. <br> <br>

<img width="198px" height="80px" src="/static/gpl.png">

<em class="grey" style="position: relative; left: 460px">
Carl Smith 2013 | Piousoft<span style="font-size: 16px">&trade;
</em>

</div></div>
'''
