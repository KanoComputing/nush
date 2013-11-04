
        # NUSH: PIPES AND BUFFER

# standard library stuff
import re
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
                radio.send('pin0', json.dumps({'jscript': 'output(pkg.string)', 'string': output}))

        # the string buffer
        self.output = ''
        
        # wait for the shell to register with the radio
        # TODO: this loop needs to block, not spin
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
        
        New lines and spaces are escaped, but not tabs, and an effort is made to
        process default representations of Python objects nicely.'''
        
        # split on each hex with one or more '>' chars after it (keeping everything)
        results = re.split(r'(0x[0-9a-f]+>+)', string)
        
        string = ''
        output = ''
        
        for i, result in enumerate(results):
        
            if i % 2 != 0: # each even index is a hex string
            
                # the chunk of text before this hex and after any earlier one
                previous = results[i-1]
                
                # the depth that the object representations are nested to 
                depth = result.count('>')
                
                # the index of the opening bracket for the outermost object representation
                start = [ match.start() for match in re.finditer('<', previous) ][-depth]
                
                # chop the start of the string and the object representation, escaping any
                # opening brackets, and adding some colour
                string += previous[:start]
                string += '<em><yell>&lt;</yell><hi>{0}{1}</hi><yell>&gt;</yell></em>'.format(
                    previous[start+1:].replace('<', '<yell>&lt;</yell>'),
                    '<dull>{0}</dull>'.format(result[:-depth])
                    )
        
        # if the length of the results is odd, there's a bit of string left after the last hex
        if len(results) % 2 != 0: string += results[-1]
        
        # now escape and highlight module and built-in representations...

        for part in re.split(r'(<.+?>)', string):
            
            if part.startswith('<module '):
                
                output += (
                    "<em><yell>&lt;</yell><hi>module <good>{0}</good> {1} <good>{2}</good>"
                    "</hi><yell>&gt;</yell></em>".format(*part[:-1].split()[1:])
                    )
                
            elif part.startswith('<built-in '):
                
                output += (
                    "<em><yell>&lt;</yell><hi>built-in {0}"
                    "</hi><yell>&gt;</yell></em>".format(' '.join(part[:-1].split()[1:]))
                    )
            
            else: output += part

        # escape any new lines and spaces, and flush
        output = output.replace('\n', '<br>')
        output = output.replace(' ', '&nbsp;')
        self.output += output


    def standard_error_mode(self, string):

        '''This method processes output according to the rules for default stderr.
        See the user docs for more information.'''

        string = '<meh><xmp>{0}</xmp></meh>'.format(string)
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
