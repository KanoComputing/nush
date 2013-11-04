
        # NUSH: SHELL EXTENSION

class Shell:

    '''This class implements a singleton, named shell, that wraps the shell clients for the
    user. They're expected to interact with the shell through the API created here.'''

    license_info = open(nush.ROOTDIR+'/static/apps/shell/license.html').read()
    
    def send(self, data):
        
        '''This method just sends a message to the shell. The shell expects packages, which
        are JSON dicts containing some JavaScript to be evaluated. There's also the option
        to pass other data in the dict, and reference it in the JavaScript as attributes
        of an object named pkg . See the user docs for more information.'''
        
        radio.send('pin0', data)


    def evaluate(self, expression, extras=None):
        
        '''This method accepts a JavaScript string, and optionally a dict of objects. It
        packages everything up and sends it to the shell, which evaluates the JavaScript
        and returns the value. This method blocks until that evaluation is complete.'''

        pin = issue_pin() # the pin used to identify the response from the client
        
        # package everything and pass it to the supereval function in the shell
        jscript = 'supereval(pkg.pin, pkg.expression, pkg)'
        package = {'jscript': jscript, 'pin': pin, 'expression': expression}
        if extras: package.update(extras)
        self.send(nush.json.dumps(package))

        ## now wait for the response, then return it...

        nush.stdin_lock.acquire()

        while True:
        
            if pin in superspace: break
            nush.stdin_lock.wait()
        
        nush.stdin_lock.release()
        return superspace.pop(pin)


    def execute(self, jscript, extras=None):
        
        '''This method sends a package to the shell, then returns None. It is used to push
        arbitrary code to the shell. Is that dangerous? Who really gives a shit.'''

        package = {'jscript': jscript}
        if extras: package.update(extras)
        self.send(nush.json.dumps(package))


    def create_feed(self, color, title, message, body=''):

        '''This method creates a feed in the shell. See the user docs for more information
        on how it works.'''

        self.send(nush.feed(color, title, message, body))


    def create_frame(self, color, title, message, path, height=16):

        '''This method creates a feed with a frame in the shell. See the user docs for more
        information on how it works.'''

        height = height * 16
        height = str(height) + 'px'
        body = '<iframe src="{0}" scrolling=yes style="height:{1}"></iframe>'
        self.create_feed(color, title, message, body.format(path, height))


    def create_tab(self, url): 
        
        '''This method takes a URL and opens a new tab in the browser, via the shell's tab.'''
        
        self.execute('window.open("{0}")'.format(url))


    def clear(self):
        
        '''This method simply clears the output feeds from the shell.'''
        
        self.execute('clear_feeds()')


    def license(self):
        
        '''This method renders the licensing information in the shell. The actual HTML string
        is at the bottom of this file, but bound to the nush module. This is an extension, so
        it has to clean up its namespace when it loads.'''

        self.create_feed('green', 'free', 'GNU General Public License', self.license_info)
        self.execute('editor.focus()')


def view(path=''):

    '''A command for viewing directories and files. It will do different things depending on
    the type of thing it is rendering. See the user docs for more information.'''

    if not path: path = os.getcwd()
    else: path = path_resolve(path)

    # if it's just a web address, done
    if nush.urlparse(path).scheme: return shell.create_tab(path)

    ## handle viewing a file...
    
    if os.path.isfile(path):
        
        ends = path.endswith

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
            body = '<img height="200" src="{0}">'.format(path)

        else: return shell.create_frame(
                'green', 'view', 'rendering the text file at <hi>{0}</hi>'.format(path),
                '/nush/builtin/editor?path=' + path,
                32
                )

    ## handle viewing a directory...

    elif os.path.isdir(path):

        message = 'rendering the directory at' if path else 'rendering the working directory, currently at'
        body = nush.dir2html(path)

    # this just deals with paths to nowhere
    else: return shell.create_feed(
        'red', 'view', 'there\'s nothing at <hi>{0}</hi>'.format(path)
        )

    # render the view feed
    message = '{0} <hi>{1}</hi>'.format(message, path)
    shell.create_feed('green', 'view', message, body)


def edit(path=''):

    '''A command for opening a text file in a new editor tab. See the user docs for more
    information.'''

    if not path: return shell.create_feed(
        'red', 'edit', 'the edit command can not be called without arguments'
        )

    tokens = path.split()

    # create a new file, if it's safe to do so
    if tokens[0] in ('-n', '-new'):

        # throw one if there's too few args
        if len(tokens) != 2: return shell.create_feed(
                'red', 'edit', 'you need to provide a path to the new file'
                )

        path = path_resolve(tokens[1])

        # throw one if the path points to an existing file
        if os.path.isfile(path): return shell.create_feed(
                'red', 'edit', 'there\'s already a file at <hi>{0}</hi>'.format(path)
                )

        ## now try and write to the new file, if it can be done without
        ## creating directories...
        
        try:
            
            with open(path, 'w') as f: f.write('')
            
        except IOError: return shell.create_feed(
            'red', 'edit', 'there\'s no path to <hi>{0}</hi>'.format(path)
            )

    ## the user wants to edit an existing file. first check that it actually
    ## does exist...
    
    else:

        path = path_resolve(path)
        if not os.path.isfile(path): return shell.create_feed(
                'red', 'edit', 'there\'s no file at <hi>{0}</hi>'.format(path)
                )

    # the file exists. tell the shell to call the builtin editor method
    return shell.execute("window.open('/nush/builtin/editor?path={0}')".format(path))


def mark(args=''):

    '''A Command for Managing Bookmarks.'''

    def update_bookmarks_file():
        
        '''This function writes the bookmarks to disk, as a JSON file.'''

        with open(nush.ROOTDIR+'/static/apps/shell/bookmarks.json', 'w') as f: f.write(nush.json.dumps(nush.BOOKMARKS))

    tokens = args.split()
    length = len(tokens)

    ## if there's no args, just show the bookmarks...

    if not tokens:

        output = ''
        for key in nush.BOOKMARKS.keys():

            output += (
                '<span class=pea>{0}</span><br><hi>{1}</hi><br><br>'
                ).format(key, nush.BOOKMARKS[key])

        if not output: return shell.create_feed('green', 'mark', 'there are no bookmarks to list')
        return shell.create_feed('green', 'mark', 'listing current bookmarks', output[:-8])

    # else if the user wants to delete a bookmark...

    if tokens[0] in ('-d', '-del', '-delete'):

        if length == 1: return shell.create_feed(
            'red', 'mark', 'you must name the bookmark you want deleting'
            )

        name = tokens[1]

        try:

            del nush.BOOKMARKS[name]
            update_bookmarks_file()
            return shell.create_feed(
                'green', 'mark', 'deleted the bookmark <hi>{0}</hi>'.format(name)
                )

        except KeyError: return shell.create_feed(
            'red', 'mark', 'there\'s no bookmark named <hi>{0}</hi>'.format(name)
            )

    # else if the user wants to create a new bookmark...

    if length == 1: name, path = tokens[0], os.getcwd()       # bookmark the current working directory
    else: name, path = tokens[1], path_resolve(tokens[0])   # bookmark the given path

    nush.BOOKMARKS[name] = path
    update_bookmarks_file()
    message = (
        'a bookmark named <hi>{0}</hi> now points to <hi>{1}</hi>'
        ).format(name, path)

    return shell.create_feed('green', 'mark', message)


def goto(path=''):

    '''A command for changing the current working directory. If no args are provided, the
    cwd is changed to the user's home directory.'''

    if not path:

        os.chdir(nush.HOME)
        message = 'the working directory is now <hi>{0}</hi>'.format(nush.HOME)
        return shell.create_feed('green', 'goto', message)

    path = path_resolve(path)

    try: os.chdir(path)
    except OSError:

        message = 'there\'s no directory at <hi>{0}</hi>'.format(path)
        return shell.create_feed('red', 'goto', message)

    body = nush.dir2html(path)
    message = 'the working directory is now <hi>{0}</hi>'.format(path)
    return shell.create_feed('green', 'goto', message, body)


def move(args=''):

    '''A command for moving files and directories from where they are to some other
    directory. It checks that no data is going to be overwritten in the process.'''
    
    tokens = args.split()
    
    # throw one if there's not enough args
    if len(tokens) != 2: return shell.create_feed(
        'red', 'move', 'you must provide two paths: <hi>.move /from /to</hi>'
        )
        
    item, destination = path_resolve(tokens[0]), path_resolve(tokens[1])
    
    # check if the item to be moved is a file or directory, throwing one if it's neither
    if os.path.isdir(item): kind = 'directory'
    elif os.path.isfile(item): kind = 'file'
    else: return shell.create_feed('red', 'move', 'there\'s nothing at <hi>{0}</hi>'.format(item))
    
    # throw one if the destination is not an existing directory
    if not os.path.isdir(destination): return shell.create_feed(
        'red', 'move', 'there\'s no directory at <hi>{0}</hi>'.format(destination)
        )
    
    # find out where the item will end up
    nupath = destination + '/' + os.path.basename(item)
    
    # throw one if this move would overwrite something else
    if os.path.exists(nupath):
        
        nukind = 'directory' if os.path.isdir(nupath) else 'file'
        return shell.create_feed(
            'red', 'move', 'a {0} already lives at <hi>{1}</hi>'.format(nukind, nupath)
            )
    
    # move the item and say so
    nush.shutil.move(item, destination)
    shell.create_feed(
        'green', 'move',
        'moved the {0} at <hi>{1}</hi> to <hi>{2}</hi>'.format(kind, item, destination)
        )


def stdo(arg=''):

    '''A command for switching the way stdout is processed. See the user docs for more
    information.'''
    
    mode = nush.pipe.expand_mode(arg)
    
    if not mode: return shell.create_feed(
        'red', 'stdo', 'there\'s no mode named <hi>{0}</hi>'.format(arg)
        )
        
    nush.pipe.stdout(mode)
    shell.create_feed(
        'green', 'stdo', 'standard out has switched to <hi>{0}</hi> mode'.format(mode)
        )


def stde(arg=''):

    '''A command for switching the way stderr is processed. See the user docs for more
    information.'''
    
    mode = nush.pipe.expand_mode(arg)
        
    if not mode: return shell.create_feed(
        'red', 'stde', 'there\'s no mode named <hi>{0}</hi>'.format(arg)
        )
        
    nush.pipe.stderr(mode)
    shell.create_feed(
        'green', 'stde', 'standard error has switched to <hi>{0}</hi> mode'.format(mode)
        )


# this is the condition object that is used by threads to block while they wait for
# input from a client. it is used by nush.superspace to notify any threads that the
# superspace has been added to
nush.stdin_lock = nush.Condition()


def input(prompt='> '):

    '''This function is available to users as a replacement for Python's builtin version.
    It is used by the StdIn class below to hook stdin calls to the shell.'''

    ## render a new stdin prompt in the shell...
    
    if prompt: prompt = '<good><xmp style=display:inline>{0}</xmp></good>'.format(prompt)
    
    pin = issue_pin()
    nush.pipe.output += '''
    <form id=%s onsubmit="return false" style=display:inline>%s<input class=stdin_prompt
    onkeyup="if (event.keyCode==13 && this.value) { submit_stdin(this.parentNode, this.value) }"
    type=text size=128 autofocus autocomplete=off></form>
    ''' %(pin, prompt)

    ## wait for the response, then return it...
    
    nush.stdin_lock.acquire()
            
    while True:
    
        if pin in superspace: break
        nush.stdin_lock.wait()
    
    nush.stdin_lock.release()
    
    return superspace.pop(pin)


# wrap sys.stdin, pointing it at the custom input function...

class StdIn:
    
    '''This class just wraps Python's stdin, hooking it to the shell, via the custom input
    function above.'''
    
    def isatty(self): return False
    def readline(self): return input()

# hook up stdin and clear up the namespace (this is an extension file)
import sys; sys.stdin = StdIn(); del sys, StdIn


## tweak the namespace...

import pdb
trace = pdb.set_trace

shell = Shell()
nush.shell = shell
nush.pipe = nush.pipes.Pipes(nush.radio)
shell.execute('connected(1)')
del Shell
