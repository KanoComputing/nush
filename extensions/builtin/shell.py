

        # NUSH 0.1 SHELL EXTENSION
        # This is Free Software (GPL)

class Shell:

    '''Wraps the shell instance for the user's namespace.'''

    def send(self, data): radio.send('pin0', data)

    def evaluate(self, expression, extras=None):

        pin = issue_pin()
        jscript = 'supereval(pkg.pin, pkg.expression, pkg)'

        package = {'jscript': jscript, 'pin': pin, 'expression': expression}
        if extras: package.update(extras)
        self.send(nush.json.dumps(package))

        while pin not in superspace: pass
        return superspace.pop(pin)

    def execute(self, jscript, extras=None):

        package = {'jscript': jscript}
        if extras: package.update(extras)
        self.send(nush.json.dumps(package))

    def prompt(self, prompt='>>>'):

        return self.evaluate('prompt(pkg.prompt)', {'prompt': prompt})

    def create_feed(self, color, title, message, body=''):

        self.send(nush.feed(color, title, message, body))

    def create_frame(self, color, title, message, path, height=16):

        height = height * 14
        height = str(height) + 'px'
        body = '<iframe src="{0}" scrolling=yes style="width: 100%; border: 1px solid #222; height: {1}"></iframe>'
        self.create_feed(color, title, message, body.format(path, height))

    def create_tab(self, url): self.execute('window.open("{0}")'.format(url))

    def clear(self): self.execute('clear_feeds()')

    def license(self):

        self.create_feed('green', 'free', 'GNU General Public License', nush.license_info)
        self.execute('editor.focus()')


# COMMAND: view
def view(path=''):

    '''Command for viewing directories and files.'''

    if not path: path = os.getcwd()
    else: path = path_resolve(path)

    ends = path.endswith

    if os.path.isfile(path):

        if ends('.sh.py'): return None # TODO

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

        else: return shell.create_frame(
                'green', 'view', 'rendering the text file at <span class=yellow>{0}</span>'.format(path),
                '/nush/builtin/editor?path=' + path,
                32
                )

    elif os.path.isdir(path):

        message = 'rendering the directory at' if path else 'rendering the working directory, currently at'
        body = nush.dir2html(path)

    else: return shell.create_feed(
        'red', 'view', 'there\'s nothing at <span class="yellow">{0}</span>'.format(path)
        )

    message = '{0} <span class="yellow">{1}</span>'.format(message, path)
    return shell.create_feed('green', 'view', message, body)


# COMMAND: edit
def edit(path=''):

    '''Command for opening a text file in a new editor tab.'''

    if not path: return shell.create_feed(
        'red', 'edit', 'the edit command can not be called without arguments'
        )

    tokens = path.split()

    if tokens[0] in ('-n', '-new'):

        if len(tokens) != 2: return shell.create_feed(
                'red', 'edit', 'you need to provide a path to the new file'
                )

        path = path_resolve(tokens[1])

        if os.path.isfile(path): return shell.create_feed(
                'red', 'edit', 'there\'s already a file at <span class=yellow>{0}</span>'.format(path)
                )

        try:
            with open(path, 'w') as f: f.write('')
        except IOError: return shell.create_feed(
            'red', 'edit', 'there\'s no path to <span class="yellow">{0}</span>'.format(path)
            )

    else:

        path = path_resolve(path)
        if not os.path.isfile(path): return shell.create_feed(
                'red', 'edit', 'there\'s no file at <span class="yellow">{0}</span>'.format(path)
                )

    return shell.execute("window.open('/nush/builtin/editor?path={0}')".format(path))


# COMMAND: mark
def mark(args=''):

    '''Command for Managing Bookmarks.'''

    def update_bookmarks_file():

        with open(nush.ROOTDIR+'/static/apps/shell/bookmarks.json', 'w') as f: f.write(nush.json.dumps(nush.BOOKMARKS))

    tokens = args.split()
    length = len(tokens)

    # show bookmarks and return...

    if not tokens:

        output = ''
        for key in nush.BOOKMARKS.keys():

            output += (
                '<span class=pea>{0}</span><br><span class=yellow>{1}</span><br><br>'
                ).format(key, nush.BOOKMARKS[key])

        if not output: return shell.create_feed('green', 'mark', 'there are no bookmarks to list')
        return shell.create_feed('green', 'mark', 'listing current bookmarks', output[:-8])

    # or delete a bookmark and return...

    if tokens[0] in ('-d', '-del', '-delete'):

        if length == 1: return shell.create_feed(
            'red', 'mark', 'you must name the bookmark you want deleting'
            )

        name = tokens[1]

        try:

            del nush.BOOKMARKS[name]
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

    nush.BOOKMARKS[name] = path
    update_bookmarks_file()
    message = (
        'a bookmark named <span class="yellow">{0}</span> now points to <span class="yellow">{1}</span>'
        ).format(name, path)

    return shell.create_feed('green', 'mark', message)
    

# COMMAND: goto
def goto(path=''):

    '''Command for changing the current working directory.'''

    if not path:

        os.chdir(nush.HOME)
        message = 'the working directory is now <span class="yellow">{0}</span>'.format(nush.HOME)
        return shell.create_feed('green', 'goto', message)

    path = path_resolve(path)

    try: os.chdir(path)
    except OSError:

        message = 'there\'s no directory at <span class="yellow">{0}</span>'.format(path)
        return shell.create_feed('red', 'goto', message)

    body = nush.dir2html(path)
    message = 'the working directory is now <span class="yellow">{0}</span><br><br>'.format(path)
    return shell.create_feed('green', 'goto', message, body)


# COMMAND: move
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
    
    nupath = destination + '/' + os.path.basename(item)
    if os.path.exists(nupath):
        
        nukind = 'directory' if os.path.isdir(nupath) else 'file'
        
        return shell.create_feed(
            'red', 'move', 'a {0} already lives at <span class=yellow>{1}</span>'.format(nukind, nupath)
            )
    
    nush.shutil.move(item, destination)
    shell.create_feed(
        'green', 'mark',
        'moved the {0} at <span class=yellow>{1}</span> to <span class=yellow>{2}</span>'.format(kind, item, destination)
        )
    
    shell.create_feed(
        'red', 'stdo', 'there\'s no mode named <span class=yellow>{0}</span>'.format(mode)
        )

# COMMAND: stdo
def stdo(arg=''):
    
    mode = nush.pipe.expand_mode(arg)
    
    if not mode: return shell.create_feed(
        'red', 'stdo', 'there\'s no mode named <span class=yellow>{0}</span>'.format(arg)
        )
        
    nush.pipe.stdout(mode)
    shell.create_feed(
        'green', 'stdo', 'standard out has switched to <span class=yellow>{0}</span> mode'.format(mode)
        )

# COMMAND: stde
def stde(arg=''):
    
    mode = nush.pipe.expand_mode(arg)
        
    if not mode: return shell.create_feed(
        'red', 'stde', 'there\'s no mode named <span class=yellow>{0}</span>'.format(arg)
        )
        
    nush.pipe.stderr(mode)
    shell.create_feed(
        'green', 'stde', 'standard error has switched to <span class=yellow>{0}</span> mode'.format(mode)
        )


# GLOBALS

shell = Shell()
input = shell.prompt
nush.shell = shell
nush.pipe = nush.pipes.Pipework(nush.radio)
shell.execute('connected(1)')
del Shell

nush.license_info = '''
NUSH is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as <br>
published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. <br> <br>

NUSH is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty <br>
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. <br> <br>

A copy of the GNU General Public License is included with NUSH, and can be found in the root directory of the <br>
application, in a file named LICENSE. <br> <br>

<img width="198px" height="80px" src="/static/gpl.png">

<span class="grey" style="position: absolute; left: 524px">
Carl Smith 2013 <span class=dull>|</span> Piousoft<span style="font-size: 16px">&trade;
</span>
'''