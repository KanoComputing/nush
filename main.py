

        # NUSH 0.3 MAIN SERVER
        # This is Free Software (GPL)


# standard library stuff
import os, sys, json
from time import sleep
from threading import Thread
from code import InteractiveInterpreter

# third party stuff
import cherrypy
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

# nush stuff
import nush # a reference to this nush module is passed into the interpreter
from nush import ROOTDIR, escape_html, path_resolve, feed, superpin

# this is where the user's optional extension files live. while the extension
# system doesn't import files directly, stuff in the directory is importable
sys.path.append(ROOTDIR+'/extensions')


class Interpreter(InteractiveInterpreter):
    
    '''This is the user's interactive interpreter. The user has no access
    to stuff outside this space unless a reference is passed in for them.
    
    Absolutely everything must, directly or indirectly, end up inside this
    namespace somewhere. Reference to runtime objects must be passed in to
    make them available to the user, including this interpreter.
    
    Anything messy or dangerous will stay inside the nush module.'''

    extensions = [] # the extensions that have been loaded, by name

    def __init__(self):

        '''This method grabs everything outside the interpreter, binding it
        all to the nush module object, making the server, radio and this
        interpreter new globals in that namespace. The nush module is
        then passed into the new interpreter.
        
        Some startup code is then executed. This code initialises some stuff
        in the nush module that references the server and radio, now they're
        available. It then imports some stuff from the nush module into the
        interpreter's namespace, so they're globals to the user.
        '''
        
        nush.server, nush.radio, nush.interpreter = server, radio, self
        
        InteractiveInterpreter.__init__(self, {'nush': nush})
        
        self.runcode(nush.namespace)


    def enter(self, code, seen=False):
        
        '''This method takes a string of code, calls self.parse on it, which
        trys to convert it to pure Python. If that fails, an error message is
        sent to the shell, else the code is executed inside the interpreter.
        
        The seen argument determines if the input is echoed in the shell. It
        is possible for clients to enter code silently, so it doesn't appear
        to be user input.'''

        code, valid = self.parse(code)

        if not valid:
            
            return radio.send('pin0', feed('red', 'line', 'the arguments were invalid'))

        if seen:

            output = '<lite>{0}</lite>'.format(escape_html(code))
            radio.send('pin0', json.dumps(
                {'jscript': 'output(pkg.string)', 'string': output}
                ))

        self.runcode(code)


    def extend(self, extension, paths, redo):
        
        '''An extension is just a named collection of files to be executed.
        
        Note: The files are not imported; they are just executed inside the
        namespace, allowing the interpreter to be extended easily.
        
        This method accepts an extension name, a list of file paths and a redo
        bool. If redo is truthy, the extension will be loaded even if it has
        been loaded already, otherwise not.
        
        An extension typically consists of one file that actually extends
        the namespace, and another, of the same name, but living in the
        extensions directory, that the end user can hack on. Any file
        that doesn't exist is simply ignored.
        
        No extension can load until the core extension is loaded, which is
        done when nush.namespace is entered at the end of self.__init__ .
        No other extension, apart from the core, can load until the shell's
        extension has loaded, so further extensions can depend on the shell
        existing and the namespace being ready to manage it.
        '''
        
        jscript = '' # shell output, if any is needed
        
        # the shell waits for the core, everything else waits for the shell
        while not 'core' in self.extensions: pass
        while extension != 'shell' and 'shell' not in self.extensions: pass
    
        # if this extension has been done, and shouldn't be redone, the
        # following block (which loads the extension) is skipped over
        if not (extension in self.extensions and not redo):
            
            # make sure the extension's in the list of done extensions
            if extension not in self.extensions: self.extensions.append(extension)

            # turn the list of paths, for files that exist, into a string of exec calls
            code = '\n'.join(
                'exec(compile(open("{0}").read(), "{0}", "exec"))'.format(ROOTDIR+path) 
                for path in paths if os.path.isfile(ROOTDIR+path)
                )
            
            # enter the code and set up some jscript to toast the extension
            self.enter(code, False)
            jscript += 'toast_extension("{0}");'.format(extension)
        
        # if this is the shell extension (a special case) update the shell client
        if extension == 'shell': jscript += 'connected(2)' 
        
        # finish by sending the jscript to the shell
        radio.send('pin0', json.dumps({'jscript': jscript}))


    def parse(self, code):
        
        '''This method is called by self.enter with the string to be entered. The
        string passed in may not be valid Python, but the string returned will be.
        If that can't be done, False is returned as the second return value. It is
        on to the caller to check that second value and handle bad input.
        
        All this method currently does is handle commands, converting something
        like the following line into the one below it:
        
            .edit -new main.py
        
            spam('-new main.py')
        
        The actual implemetation sucks, but it does work in practice, and can be
        improved without fallout.'''

        code = code.strip()

        # if it's just python, there's nothing to do
        if not code.startswith('.'): return code, True

        # split the input into tokens
        tokens = code[1:].split()

        # if there's no args, just add parens to the callable and return
        if len(tokens) == 1: return '{0}()'.format(tokens[0]), True

        # get the whole arg string (args are parsed by the callable)
        arg = code[len(tokens[0])+2:].strip()

        ## quote the arg as cleanly as possible, returning bad news if it
        ## can't be wrapped in quotes without adding escape characters
        ## it's this string that's executed and then rendered in the shell

        def either_end(char): return arg.startswith(char) or arg.endswith(char)

        if   "'" not in arg: template = "{0}('{1}')"
        elif '"' not in arg: template = '{0}("{1}")'
        elif "'''" not in arg and not either_end("'"): template = "{0}('''{1}''')"
        elif '"""' not in arg and not either_end('"'): template = '{0}("""{1}""")'
        else: return '', False

        # format the template and return the result
        return template.format(tokens[0], code[len(tokens[0])+2:]), True


class Socket(WebSocket):
    
    '''This class subclasses the ws4py websocket, allowing websocket
    clients to be wrapped by the radio abstraction.'''

    def __init__(self, *args, **kargs):
        
        '''Creates and registers new websockets with the radio.'''

        WebSocket.__init__(self, *args, **kargs)
    
        # channel names are passed in the url, i.e. /ws/chan0/chan1
        # this line extracts them into a list of channel names
        channels = str(self.environ['REQUEST_URI'])[2:-1].split('/')[2:]
        
        # register the current socket's send method as the callable
        radio.register(channels, self.send)


    def closed(self, code, reason=None):

        '''Deregisters (removes) websocket clients from the radio's
        dictionary of handlers.'''
        
        for channel, handlers in radio.channels.items():

            if self.send in handlers: handlers.remove(self.send)


class Radio:

    '''This class is used to create the radio object, a singleton that wraps
    the websocket. The radio is a global in the user's namespace. It is also
    accessable from external clients, via the server. Javascript clients use
    wrappers around websockets to interface with the radio.
    
    Channels are just unique strings (among channel names). Any callable can
    be registered to any number of channels, and each channel can have any
    number of callables registered to it.
    
    Messages are strings. Use JSON if you need to send more complex data.
    '''

    channels  = {} # a dict mapping each channel name to a list of callables

    def register(self, channels, handler):
        
        '''This method accepts a channel name, as a string, or a list of them
        (as a list of strings), and a handler (any callable). The callable is
        registered to receive messages on each of the channels.'''

        if type(channels) is str: channels = [channels]

        for channel in channels:

            # if the channel exists, append the callable to it's handlers list
            # if it does not not, create a list with only the handler in
            if channel in self.channels: self.channels[channel].append(handler)
            else: self.channels[channel] = [handler]


    def send(self, channels, message):

        '''This method accepts a channel name, as a string, or a list of them
        (as a list of strings), and a message (also a string). The message is
        sent to each handler that's registered to each of the channels.'''

        if type(channels) is str: channels = [channels]

        for channel in channels:

            for handler in self.channels[channel]: handler(message)


class Server:

    '''This is the main server that provides communication between the user's
    namespace and external clients. It lives inside the nush module. Other
    objects exist in the global namespace that abstract it.
    
    The nush module will attach another handler to this server, called nush.
    That handler lives inside a singleton that provides an API that the user
    can use to assign handler functions and classes ~ where each method acts
    as a handler ~ to the server at runtime.'''

    @cherrypy.expose # serve the websocket (using the ws4py plugin)
    def ws(self, *channels): pass

    @cherrypy.expose # serve the shell client as a static file
    def index(self): return open(ROOTDIR+'/static/apps/shell/shell.html')

    @cherrypy.expose # expose the interpreter's enter method
    def enter(self):

        data = json.loads(cherrypy.request.body.read().decode())
        interpreter.enter(data['code'], data['seen'])

    @cherrypy.expose # expose the interpreter's extend method
    def extend(self, extension, redo):

        paths = json.loads(cherrypy.request.body.read().decode())
        interpreter.extend(extension, paths, redo=='true')

    @cherrypy.expose # save a text file (needs to work without core for debugging)
    def save_file(self):

        data = json.loads(cherrypy.request.body.read().decode())
        with open(data['path'], 'w') as f: f.write(data['content'])


# globals
radio = Radio()
server = Server()
interpreter = Interpreter()

# set the host and port number
cherrypy.config.update({
    'server.socket_host': '127.0.0.1',
    'server.socket_port': 10002,
    'environment': 'production' # comment this out to debug
    })

# plumb in ws4py's cherrypy websocket plugin
WebSocketPlugin(cherrypy.engine).subscribe()
cherrypy.tools.websocket = WebSocketTool()

# serve static resources, the whole filesystem and the websocket
cherrypy.quickstart(server, '/', {

    '/static': { # serve static files
        'tools.staticdir.on': True,
        'tools.staticdir.dir': ROOTDIR+'/static'
        },

    '/': { # serve the filesystem
        'tools.staticdir.on': True,
        'tools.staticdir.dir': '/'
        },

    '/ws': { # serve the websocket
        'tools.websocket.on': True,
        'tools.websocket.handler_cls': Socket

        }})
