
        # NUSH: CORE NAMESPACE

# standard library stuff
import os
import cgi
import json
import shutil
import mimetypes
from time import sleep
from threading import Thread, Condition
from subprocess import Popen, PIPE
from string import ascii_letters, digits
from urllib.parse import urlparse

# third party stuff
import cherrypy

# nush stuff
import pipes

class DomainsManager:

    '''This class defines a singleton, named domains, which wraps the server, allowing
    instances of classes to be registered to domains, which are unique strings amongst
    domain names. Any instance so registered exposes each of its methods as request
    handlers at that domain.

    The handle method will become the server's nush method. Registered domain handlers
    live in their domain, inside /nush . An instance registering the domain spam, with
    a method named eggs, exposes that method via /nush/spam/eggs .
    '''

    domains = {} # a mapping of domain names to instances of handler classes

    def register(self, domain, seen=True):

        '''This method accepts an instance of a class that has a domains attribute, and
        registers the domain to that instance. This can be done without the shell being
        available by making the seen arg falsey.'''

        self.domains[domain.domain] = domain
        if seen: shell.execute('toastr.success("NEW DOMAIN: {0}")'.format(domain.domain))


    def read_post(self):

        '''This method is used by self.handle. It returns the POST data if there was any,
        else it returns None.'''

        try: return cherrypy.request.body.read().decode()
        except: return None


    def handle(self, *args, **kargs):

        '''This method becomes the server's nush method, handling all calls that begin at
        /nush . It simply passes any call and its arguments to the correct handler.'''

        args = list(args)
        data = self.read_post()

        domain = self.domains[args.pop(0)]
        method = args.pop(0)

        if data != None: return getattr(domain, method)(data, *args, **kargs)
        else: return getattr(domain, method)(*args, **kargs)

    handle.exposed = True # expose the handler


class OrphanHandlers:

    '''This implements an empty handler class that will be registered to the handlers
    domain, and made available to users as a global called handlers. Users can then
    register simple functions as handlers. The following code makes some_callable
    available at /nush/handlers/spam :

        handlers.spam = some_callable

    '''

    domain = 'handlers'


class CoreBuiltIns:

    '''This implements a class handler, registered at /nush/builtin . It holds all the
    builtin handlers that are not hardcoded into the server.'''

    domain = 'builtin'

    def issue_pin(self):

        '''This method just exposes the superpin function.'''

        return superpin()


    def superspace(self, data=None):

        '''This method allows clients to update and/or get a copy of the superspace.'''

        if data: superspace.update(json.loads(data))
        return json.dumps(superspace.space)


    def editor(self, path):

        '''This method serves editor instances. It takes a path to the file that's to be
        edited and templates editor.html before serving it.

        Note that the file's content is not placed inside the instance when it's served,
        as the content gets rendered by the browser. Instead, the templating injects the
        information the editor instance needs to load. The instance will then fetch the
        content with an ajax call to self.load_file .'''

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


    def load_file(self, path, timestamp):

        '''This method simply serves the contents of a text file, based on a path.'''

        return open(path)


    def radio_send(self, data):

        '''This method just exposes the radio object's send method to clients.'''

        radio.send(*json.loads(data))


def find(path):

    '''This function takes a breadcrumbs path and returns the thing it evaluates to, from
    within the interpreter. For example, if the path is 'a.b.c', then a reference to the
    object a.b.c from the user's namespace would be returned. If the expression does not
    evaluate, this function returns None.'''

    names = path.split('.')
    name  = names.pop(0)

    try: obj = interpreter.locals[name]
    except KeyError:

        try: obj = __builtins__[name]
        except KeyError: return None

    try:

        for name in names: obj = getattr(obj, name)
        return obj

    except AttributeError: return None


class Finder:

    def __init__(self):

        self.home, self.root = HOME, ROOTDIR
        self.statics = []

    def resolve(self, path): return path_resolve(path)

    def is_url(self, path): return True if urlparse(self.resolve(path)).scheme else False

    def open(self, path, mode='r'): return open(self.resolve(path), mode)

    def read(self, path): return open(self.resolve(path)).read()

    def write(self, path, content): open(self.resolve(path), 'w').write(content)

    def find_static(self, *args):

        '''This method is assigned to handle all requests to /static . It takes
        the request path, minus the static part, and concatenates it to each of
        the paths in self.statics to see if it produces a path to a file. If it
        does, the file's returned, else a 404 Error.

        The idea is that users can put stuff in their own directories, and have
        them served as static files, by appending the directory to self.statics
        and requesting /static/path/to/file.html . The first file found will be
        returned immediately, and self.statics is iterated over in order.

        A final check is done to see if the file lives in ./nush/static , which
        acts like a JavaScript Standard Library for users, and holds all nush's
        own stuff.'''

        path = '/'.join(args)

        for static in self.statics:

            if os.path.isfile(static+path):

                return cherrypy.lib.static.serve_file(static+path)

        if os.path.isfile(self.root+'/static/'+path):

            return cherrypy.lib.static.serve_file(self.root+'/static/'+path)

        return cherrypy.HTTPError(status=404, message='No file at *'+path)

    find_static.exposed = True


class Superspace:

    space = {'SUPERPIN': 0}

    def __iter__(self): return ( key for key in self.space )

    def items(self): return self.space.items()

    def pop(self, item):

        '''This method blocks every thread while it pops an item from the superspace.
        It will also call stdin_lock.notifyAll, so that threads that want to block
        and check if a key was removed can do.'''

        with lock:

            stdin_lock.acquire()
            item = self.space.pop(item)
            stdin_lock.notifyAll()
            stdin_lock.release()

        return item


    def update(self, data):

        '''This method blocks every thread until it's updated the superspace. It will
        also call stdin_lock.notifyAll, so that threads that're blocking until a key
        becomes available will know to check for it. The shell's input function uses
        this to block until prompts to return something.'''

        with lock:

            stdin_lock.acquire()
            self.space.update(data)
            stdin_lock.notifyAll()
            stdin_lock.release()


    def remove(self, keys):

        '''This method blocks every thread until it's removed one or more items from
        the superspace. It will also call stdin_lock.notifyAll, so that threads that
        want to block and check if a key was removed can do.'''

        if type(keys) == str: keys = [keys]

        with lock:

            stdin_lock.acquire()
            for key in keys: del self.space[key]
            stdin_lock.notifyAll()
            stdin_lock.release()


def superpin():

    '''This function increments superspace['superpin'], then generates a pin, a string
    beginning with 'pin', followed by the superpin as a string. i.e. pin1 . It can be
    accessed by clients, through wrappers, so that any process can get a universally
    unique string, which can be used for anything that needs one, such as keys for
    the superspace and HTML element id values.'''

    superspace.space['SUPERPIN'] += 1
    return 'pin' + str(superspace.space['SUPERPIN'])


def feed(color, title, message, body=''):

    '''Generate a new feed package with an optional body. This is used internally, but is
    exposed through methods of the shell singleton.'''

    if body: body = '<div class=padded_feed>{0}</div>'.format(body)

    feed = '''
        <span class="{0}">{1}</span> <span class=grey>#</span><span style="float:right"
        onclick="this.parentNode.parentNode.removeChild(this.parentNode); editor.focus()">
        <span style="padding-right: 4px" class="dull kill_button hint--left hint--bounce"
            data-hint="Delete This Feed">x</span></span>
        {2}{3}'''.format(color, title, message, body)

    return json.dumps({'feed': feed, 'jscript': 'create_feed(pkg.feed)'})


def escape_html(html):

    '''This function just wraps a string in xmp tags. This seems to be simpler and more
    robust than escaping characters and adding br tags, or using pre tags.

    It's tricky trying to wrap stdout and stderr, handle REPLs like help's and pdb's and
    render input prompts, all in the right order, and all while keeping certain things
    inline, and putting single whitelines between each block.'''

    return '<xmp>{0}</xmp>'.format(html)


def path_resolve(path):

    '''This function patches the way paths are expanded, so they're consistant.'''

    # don't expand comlpete urls
    if not path or urlparse(path).scheme: return path

    path = path_expand(path)

    # chop off any trailing slash
    if path != '/' and path.endswith('/'): path = path[:-1]

    # strip double slashes (when going up from root as cwd)
    return path[1:] if path.startswith('//') else path


def path_expand(path):

    '''This function takes a relative path, which may use a bookmark, and returns an
    absolute path.'''

    starts = path.startswith
    normalise = os.path.normpath

    if   starts('/'):   return path
    elif starts('./'):  return normalise(os.getcwd() + path[1:])
    elif starts('../'): return normalise(os.path.dirname(os.getcwd()) + path[2:])
    elif starts('~/'):  return os.path.expanduser("~") + path[1:]
    elif starts('|'):

        try:

            if '/' not in path: return BOOKMARKS[path[1:]]

            name = path[1:path.find('/')]
            tail = path[path.find('/'):]
            return BOOKMARKS[name] + tail

        except KeyError: return path

    else: return os.getcwd() + '/' + path


def dir2html(path):

    '''This function renders a directory's contents as HTML. It is used by the view and
    goto commands. It 'syntax highlights' items by type, and sorts them alphabetically,
    with directories before files regardless.'''

    dirs, files = '', ''
    items = os.listdir(path)
    items.sort()

    for item in items:

        ends = item.endswith
        full_path = '{0}/{1}'.format(path, item)

        if os.path.isdir(full_path):

            dirs += '''<directory>{0}</directory><br>'''.format(item)
            continue

        elif ends('.py'): tag = 'python_file'
        elif ends('.zip'): tag = 'archive_file'
        elif item.startswith('.'): tag = 'hidden_file'
        elif item.startswith('README') or item.startswith('LICENSE'): tag = 'readme_file'
        elif ends('.png') or ends('.jpg') or ends('.jpeg') or ends('.mp4'): tag = 'media_file'
        elif ends('.html') or ends('.md') or ends('.css') or ends('.js') or ends('.json'): tag = 'web_file'
        else: tag = 'file'

        files += '''<{0}>{1}</{0}><br>'''.format(tag, item)

    return dirs + files if dirs or files else '<span class=dull>(this directory is empty)</span>'


def bosh(line):

    '''Get the output of a system command as a string. This is unused, and is experimental.'''

    stdout, stderr = Popen([line], shell=True, stdout=PIPE, stderr=PIPE).communicate()
    output = stdout if stdout else stderr
    return(output.decode())


def init():

    '''This function is called after this module has been imported and placed inside the
    interpreter's namespace. The interpreter's __init__ method binds references to the
    server, radio and to itself to this module, making them globals here. Once that is
    done, this module can safely reference them, but not before (on import). The job
    of this function is to tweak things once the objects are available.'''

    global issue_pin, domains, handlers, builtin_handlers, finder

    issue_pin = superpin

    # attach the finder's statics method to server at /static
    finder = Finder()
    server.static = finder.find_static

    # attach the domains manager to the server at /nush
    domains = DomainsManager()
    server.nush = domains.handle

    # register the empty handler class to /nush/handlers and
    # the builtin handler class to /nush/builtin
    handlers = OrphanHandlers()
    builtin_handlers = CoreBuiltIns()
    domains.register(handlers, False)
    domains.register(builtin_handlers, False)


## set up some globals...

superspace = Superspace()

# the current user's home directory
HOME = os.path.expanduser("~")

# get a path to this application's root directory
ROOTDIR = os.path.dirname(os.path.abspath(__file__))

# load the bookmarks.json file into a dict
BOOKMARKS = json.loads(open(ROOTDIR+'/static/apps/shell/bookmarks.json').read())

# this code is executed inside the interpreter when it's created. it calls the init
# method from this module, then imports a bunch of stuff from the module afterwards
# while the code doesn't really /use/ the extensions system, it registers itself as
# an extension, allowing dependent extensions to load safely
namespace = '''
import os
nush.init()
from nush import issue_pin
from nush import superspace, finder
from nush import handlers, domains, radio
nush.interpreter.extensions.append('core')
'''