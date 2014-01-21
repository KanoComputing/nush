
    # NUSH: MAIN SCRIPT

# the batteries
import os, sys, json, types
from time import sleep
from threading import Thread, Lock
from code import InteractiveConsole

# the cherryade
import cherrypy
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

# our stuff
import nush # a reference to this module is passed into the interpreter
from nush import ROOTDIR, escape_html, path_resolve, feed, superpin

# these files should be importable by the user
sys.path.append(ROOTDIR+'/extensions')
sys.path.append(".")


class Interpreter(InteractiveConsole):

    ''' The User's Interactive Interpreter

    The user has no access to objects outside of an Interpreter instance
    unless references are passed in to it when it's created. Pretty much
    everything in this application must have a reference passed into the
    interpreter's namespace, so the user can hack it. The references are
    bound to the nush module, which is the only object directly added to
    the namespace. Anything messy or dangerous will stay inside the nush
    module; wrapper objects in the global namespace provide a documented
    API.'''

    extensions = []    # the extensions that have been loaded, by name
    line_history = []  # the shell input history

    def __init__(self):

        '''This method grabs everything outside the interpreter and binds
        it to the nush module object, which makes the server, radio, lock
        and interpreter globals in that namespace. Then the module object
        is passed into the new interpreter. Some startup code is then run
        to initialise the nush module [now that stuff like the server and
        radio are available]. The code then imports some bits [from nush]
        into the interpreter's namespace, so they're globals to the user.
        '''

        nush.server, nush.radio, nush.lock, nush.interpreter = (
            server, radio, lock, self
            )

        InteractiveConsole.__init__(self, {'nush': nush})

        self.runcode(nush.namespace)


    def enter(self, string, seen=False):

        '''This method takes a string of code; if it's a command, then the
        callable gets called [or an error is handled]. otherwise the input
        string is executed in the interpreter.

        The truthiness of the seen argument determines whether the input is
        echoed to the shell. It is possible [actually commonplace] for code
        to be executed silently, so it doesn't appear to be user input.'''

        string = string.strip()

        # handle output...

        if seen:

            radio.send('pin0', json.dumps({
                'jscript': 'output(pkg.string)',
                'string': '<lite><xmp>{0}</xmp></lite>'.format(string)
                    }))

            self.line_history = [
                line for line in self.line_history if line != string
                ]

            self.line_history.append(string)

        # handle commands...

        def opps(error, string): nush.pipe.standard_error(error, string, None)

        if string.startswith('.'):

            if '\n' in string:

                if seen: return opps(SyntaxError, 'commands must be one liners')

            call = string[1:].split()[0]      # everything before the first space
            args = string[len(call)+2:]       # everything after the first space
            args = [args] if args else []     # a list of zero to one arg
            func = nush.finder.inflate(call)  # a reference to the callable object

            if func is None: return opps(NameError, "name '%s' is not defined" % call)
            if not callable(func): return opps(TypeError, 'commands must use a callable')

            try: func(*args)
            except: pass
            return None

        # handle expressions and blocks...

        try:
            
            output = eval(string.strip(), interpreter.locals)
            if output is not None: nush.pipe.standard_out(output)

        except: self.runcode(string)


    def extend(self, extension, paths, redo):

        '''An extension is just a named collection of files to be executed.

        Note: The files are not imported; they are just executed inside the
        namespace, allowing the interpreter to be extended easily.

        This method accepts an extension name, a list of paths to files and
        a redo bool. If redo is truthy, the extension will be loaded even
        if it has been loaded already, otherwise not.

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


class Socket(WebSocket):

    '''This class subclasses the ws4py websocket, and allows websocket
    clients to be wrapped by the radio abstraction.'''

    def __init__(self, *args, **kargs):

        '''New websockets can be registered with the radio on creation.
        Channel names can be passed in the URL, for example:

            ws://localhost:1002/ws/chan0/chan1

        A socket may be created with no channels, and then register one
        or more later on. This is how client-side Radio actually works.
        '''

        WebSocket.__init__(self, *args, **kargs)

        # derive a list of zero or more channels from the url
        channels = str(self.environ['REQUEST_URI'])[2:-1].split('/')[2:]

        # if channels is empty, this does nothing
        radio.register(channels, self.send, True)


    def closed(self, code, reason=None):

        '''This method deregisters a websocket client from the radio.'''

        radio.deregister(self.send)


    def received_message(self, message):

        '''This method receives all messages sent by websocket clients,
        but it is currently only used to allow clients to register more
        channels.'''

        channels = json.loads(message.data.decode())
        radio.register(channels, self.send, True)


class MessageHandler:

    '''This class is used by the Radio.register method. The radio stores
    each handler that's registered as a MessageHandler instance. This is
    mainly done to allow the channel and message data to be stringified
    automatically for those handlers that can only receive one arg as a
    message (websockets), while not requiring local Python functions to
    receive their args inside a JSON string.'''

    def __init__(self, handler, stringify=False):

        self.handler = handler
        self.stringify = stringify

    def send(self, channel, message):

        if self.stringify:

            message = json.dumps({'channel': channel, 'message': message})
            self.handler(message)

        else: self.handler(channel, message)


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

    def register(self, channels, handler, stringify=False):

        '''This method accepts a channel name, as a string, or a list of them
        (as a list of strings), and a handler (any callable). The callable is
        registered to receive messages on each of the channels.
        '''

        handler = MessageHandler(handler, stringify)

        if type(channels) is str: channels = [channels]

        with lock: # lock every thread for now; this should never take long

            for channel in channels:

                if channel in self.channels:

                    self.channels[channel].append(handler)

                else: self.channels[channel] = [handler]


    def deregister(self, dead_handler):

        '''This method deregisters every reference to a previously registered
        handler, and then deletes any channels that end up with no registered
        handlers as a result.'''

        # this method has to delete stuff from the objects it iterates over
        # and it can be called in multiple threads, so it looks a bit hairy
        # [starting to question the struct, but this is just clean up code]

        dead_message_handlers = []

        with lock: # lock every thread for now; this should never take long

            # first find, then delete every reference to the handler...

            for message_handlers in radio.channels.values():

                for message_handler in message_handlers:

                    if message_handler.handler == dead_handler:

                        dead_message_handlers.append(message_handler)

                for dead_message_handler in dead_message_handlers:

                    message_handlers.remove(dead_message_handler)

                dead_message_handlers = []

            # now delete any channels without a handler...

            empty_channels = []

            for channel in radio.channels:

                if not radio.channels[channel]: empty_channels.append(channel)

            for empty_channel in empty_channels: del radio.channels[empty_channel]


    def send(self, channels, message):

        '''This method accepts a channel name, as a string, or a list of them
        (as a list of strings), and a message (also a string). The message is
        sent to each handler that's registered to each of the channels.'''

        if type(channels) is str: channels = [channels]

        for channel in channels:

            if channel not in self.channels: return

            for handler in self.channels[channel]:

                handler.send(channel, message)


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

    @cherrypy.expose # serve the interpreter's input history
    def line_history(self): return json.dumps(interpreter.line_history)

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
        path, content = data['path'], data['content']

        try: open(path, 'w').write(content)
        except IOError: return 'io_fail'
        return 'success'


# globals
lock = Lock()
radio = Radio()
server = Server()
interpreter = Interpreter()

# set the host and port number
cherrypy.config.update({
    'server.socket_host': '127.0.0.1',
    'server.socket_port': 10002,
    'environment': 'production'
    })

# plumb in ws4py's cherrypy websocket plugin
WebSocketPlugin(cherrypy.engine).subscribe()
cherrypy.tools.websocket = WebSocketTool()

# start serving everything
cherrypy.quickstart(server, '/', {
    '/ws': {
        'tools.websocket.on': True,
        'tools.websocket.handler_cls': Socket
        },
    '/static': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': ROOTDIR + '/static'
        },
    '/': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': '/'
        }}
    )