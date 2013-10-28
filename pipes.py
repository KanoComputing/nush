

        # NUSH 0.3 PIPES AND BUFFER
        # This is Free Software (GPL)


# standard library stuff
import sys
import cgi
import json
from time import sleep
from threading import Thread


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
        to exist, redirects stdout and stderr to the default processors, the
        starts the flush function spinning.
        
        This whole thing needs revisiting, but seems to work well nonetheless.
        '''
        
        def flush():
    
            '''This function keeps a loop running in it's own thread, writting any
            output to the shell every 0.005 seconds.'''
            
            while True:
    
                sleep(0.005)
                if not self.output: continue
                output, self.output = self.output, ''
                radio.send('pin0', json.dumps({'jscript': 'output(pkg.string)', 'string': output}))

        # the string buffer
        self.output = ''
        
        # wait for the shell to register with the radio (pin0 is reserved for the shell)
        while 'pin0' not in radio.channels: pass
        
        # redirect stdout and stderr to wrapper methods
        sys.stdout.write = self.standard_out_mode
        sys.stderr.write = self.standard_error_mode
        
        # start flusher thread
        thread = Thread(target=flush)
        thread.daemon = True
        thread.start()


    def expand_mode(self, mode):
        
        '''This function just converts aliases for output processing modes into
        normalised names.'''
        
        if not mode: return 'standard'
        if mode in ('h', 'html'): return 'html'
        if mode in ('t', 'term', 'terminal'): return 'terminal'
        return False


    def standard_out_mode(self, string):

        '''This method processes output according to the rules for default stdout.
        See the user docs for more information.'''

        string = string.replace('\n', '<br>')
        string = string.replace(' ', '&nbsp;')
        self.output += string


    def standard_error_mode(self, string):

        '''This method processes output according to the rules for default stderr.
        See the user docs for more information.'''

        string = '<meh><xmp style=display:inline>{0}</xmp></meh>'.format(string)
        self.output += string
    
    def terminal_mode(self, string):

        '''This method processes output, emuulating a terminal.'''

        string = '<xmp style=display:inline>{0}</xmp>'.format(string)
        self.output += string


    def html_mode(self, string):
        
        '''This method is a no-op; it doesn't process the output at all. It is used
        for pushing raw HTML to the shell.'''
        
        self.output += string


    def stdout(self, mode):
        
        '''This method attaches a different processing method to stdout.'''
        
        if mode == 'standard': sys.stdout.write = self.standard_out_mode
        else: sys.stdout.write = getattr(self, mode + '_mode')


    def stderr(self, mode):
        
        '''This method attaches a different processing method to stdout.'''        
        
        if mode == 'standard': sys.stderr.write = self.standard_error_mode
        else: sys.stderr.write = getattr(self, mode + '_mode')
