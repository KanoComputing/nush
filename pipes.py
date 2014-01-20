
        # NUSH: PIPES AND BUFFER

# standard library stuff
import sys
import cgi
import json
from time import sleep
from threading import Thread
from html.parser import HTMLParser

class Pipes:

    '''This class implements a singleton that wraps stdout and stderr, processing
    them on their way to the shell. It also combines processed output in a string
    buffer that is pushed to the shell every 0.005 seconds, unless it's empty.

    The buffer prevents Chrome from choking on websocket messages when there's a
    high number of outputs per second. This buffer isn't sophisticated, but it
    seems to work fine in practice.'''

    def __init__(self, radio):

        '''This method defines a function that puts a loop in another thread and
        leaves it running forever. That function actually writes any processed
        output to the shell.

        This method initialises a string buffer, waits in a busy loop for the shell
        to exist, redirects stdout and stderr to the default processors, then
        starts the flush function spinning.

        This is all done to prevent the interpreter from flooding the shell client
        with websocket requests when handling one or more print loops. Rendering
        becomes really bad if thousands of stdout calls are made rapidly without
        the buffer.

        This whole thing needs revisiting, but seems to work well for now.
        '''

        def flush():

            '''This function keeps a loop running in it's own thread, writting any
            output to the shell every 0.005 seconds.'''

            while True:

                sleep(0.005)
                if not self.output: continue
                output, self.output = self.output, ''
                radio.send('pin0', json.dumps(
                    {'jscript': 'output(pkg.string)', 'string': output})
                    )

        # the string buffer
        self.output = ''

        # wait for the shell to register with the radio
        # TODO: this loop needs to block, not spin
        while 'pin0' not in radio.channels: pass

        # redirect stdout and stderr to wrapper methods
        sys.stdout.write = self.standard_out

        # start flusher thread
        thread = Thread(target=flush)
        thread.daemon = True
        thread.start()


    def render(self, arg):
            
        if hasattr(arg, '__html__'): return arg.__html__()
        return cgi.escape(str(arg)).replace('\n', '<br>')


    def standard_put(self, *args, sep=''):
        
        output = []
        
        for arg in args:
    
            if type(arg) is str: output.append(arg)
            else: output.append(self.render(arg))

        self.output += sep.join(output)


    def standard_out(self, output):

        '''This method processes output, emulating the Interactive Interpreter.'''

        self.output += '<xmp style=display:inline>{0}</xmp>'.format(output)


    def standard_error(self, error, value, traceback):

        '''This method processes stderr, adding a bit of color and so on.'''

        traceback = str(traceback) + '<br>' if traceback else ''
        args = (traceback, error.__name__, cgi.escape(str(value)))
        self.output += '{0}<bad>{1}</bad> <dull>#</dull> <hi>{2}</hi>'.format(*args)
