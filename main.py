

        # NUSH 0.2 MAIN SERVER
        # This is Free Software (GPL)


import os, sys, json
from time import sleep
from threading import Thread
from code import InteractiveInterpreter

import cherrypy
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

import nush
from nush import ROOTDIR, escape_html, path_resolve, feed, superpin

sys.path.append(ROOTDIR+'/extensions')


class Interpreter(InteractiveInterpreter):
    
    '''The users interactive interpreter.'''

    def __init__(self):

        self.extensions = []

        nush.server, nush.radio, nush.interpreter = server, radio, self

        InteractiveInterpreter.__init__(self, {'nush': nush})

        self.runcode(nush.namespace)


    def enter(self, code, seen=False):

        code, valid = self.parse(code)

        if not valid: return False

        if seen:

            output = '<lite>{0}</lite>'.format(escape_html(code))
            radio.send('pin0', json.dumps(
                {'jscript': 'output(pkg.string)', 'string': output}
                ))

        self.runcode(code)
        return True


    def extend(self, extension, paths, redo):
        
        jscript = ''
        
        # the shell waits for the core, everything else waits for the shell
        while not 'core' in self.extensions: pass
        while extension != 'shell' and 'shell' not in self.extensions: pass
    
        # if this extension has been done and shouldn't be redone, return
        if extension in self.extensions and not redo: do = False
        else: do = True

        if do:
            
            # make sure it's in the list of done extensions
            if extension not in self.extensions: self.extensions.append(extension)

            # turn the list of paths into the lines of code to be executed
            code = '\n'.join(
                'exec(compile(open("{0}").read(), "{0}", "exec"))'.format(ROOTDIR+path) 
                for path in paths if os.path.isfile(ROOTDIR+path)
                )
            
            self.enter(code, False)
        
            jscript += 'toast_extension("{0}");'.format(extension)
        
        if extension == 'shell': jscript += 'connected(2)' 
        radio.send('pin0', json.dumps({'jscript': jscript}))


    def parse(self, code):

        code = code.strip()

        # if it's just python, we're done
        if not code.startswith('.'): return code, True

        # split the input into tokens
        tokens = code[1:].split()

        # if there's no args, just add parens to the callable and return
        if len(tokens) == 1: return '{0}()'.format(tokens[0]), True

        # get the whole arg string (args are parsed by the callable)
        arg = code[len(tokens[0])+2:].strip()

        ## quote the arg as cleanly a possible, returning bad news if it
        ## can't be wrapped in quotes without adding escape characters...

        def either_end(char): return arg.startswith(char) or arg.endswith(char)

        if   "'" not in arg: template = "{0}('{1}')"
        elif '"' not in arg: template = '{0}("{1}")'
        elif "'''" not in arg and not either_end("'"): template = "{0}('''{1}''')"
        elif '"""' not in arg and not either_end('"'): template = '{0}("""{1}""")'
        else: return '', False

        return template.format(tokens[0], code[len(tokens[0])+2:]), True


class Socket(WebSocket):

    def __init__(self, *args, **kargs):

        WebSocket.__init__(self, *args, **kargs)

        channels = str(self.environ['REQUEST_URI'])[2:-1].split('/')[2:]
        radio.register(channels, self.send)

    def __str__(self): return self.environ['REQUEST_URI']

    def closed(self, code, reason=None):

        for channel, handlers in radio.channels.items():

            if self.send in handlers: handlers.remove(self.send)

    def received_message(self, message): print(message.data)


class Radio:

    channels  = {}

    def register(self, channels, handler):

        if type(channels) is str: channels = [channels]

        for channel in channels:

            if channel in self.channels: self.channels[channel].append(handler)
            else: self.channels[channel] = [handler]

    def send(self, channels, message):

        if type(channels) is str: channels = [channels]

        for channel in channels:

            for handler in self.channels[channel]: handler(message)


class Server:

    @cherrypy.expose # serve the websocket
    def ws(self, *channels): pass

    @cherrypy.expose # serve the shell
    def index(self): return open(ROOTDIR+'/static/apps/shell/shell.html')

    @cherrypy.expose # create a new interpreter
    def interpreter(self):

        global interpreter
        interpreter = Droidspace()

    @cherrypy.expose # expose the interpreter's enter method
    def enter(self):

        data = json.loads(cherrypy.request.body.read().decode())
        valid = interpreter.enter(data['code'], data['seen'])
        if not valid: radio.send('pin0', feed('red', 'line', 'the arguments were invalid'))

    @cherrypy.expose # expose the interpreter's extend method
    def extend(self, extension, redo):

        paths = json.loads(cherrypy.request.body.read().decode())
        interpreter.extend(extension, paths, redo=='true')

    @cherrypy.expose # save a text file
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
    'environment': 'embedded'
    })

# plumb in ws4py's cherrypy websocket plugin
WebSocketPlugin(cherrypy.engine).subscribe()
cherrypy.tools.websocket = WebSocketTool()

cherrypy.engine.timeout_monitor.unsubscribe()
cherrypy.engine.autoreload.unsubscribe()

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
