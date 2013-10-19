

        # NUSH 0.1 PIPES AND BUFFER
        # This is Free Software (GPL)


import sys
import cgi
import json

from time import sleep
from threading import Thread


class Pipework:

    def __init__(self, radio):

        def flush():
    
            while True:
    
                sleep(0.005)
                if not self.output: continue
                output, self.output = self.output, ''
                radio.send('pin0', json.dumps({'jscript': 'output(pkg.string)', 'string': output}))

        self.output = ''
        
        while 'pin0' not in radio.channels: pass
        
        sys.stdout.write = self.standard_out_mode
        sys.stderr.write = self.standard_error_mode
        
        thread = Thread(target=flush)
        thread.daemon = True
        thread.start()

    def expand_mode(self, mode):
        
        if not mode: return 'standard'
        if mode in ('h', 'html'): return 'html'
        if mode in ('t', 'term', 'terminal'): return 'terminal'
        return False
        
    def standard_out_mode(self, string):

        string = string.replace('\n', '<br>')
        string = string.replace(' ', '&nbsp;')
        self.output += string
        
    def standard_error_mode(self, string):

        string = '<xmp style=display:inline class=pea>{0}</xmp>'.format(string)
        self.output += string
    
    def terminal_mode(self, string):

        string = '<xmp style=display:inline>{0}</xmp>'.format(string)
        self.output += string

    def html_mode(self, string): self.output += string

    def stdout(self, mode):
        
        if mode == 'standard': sys.stdout.write = self.standard_out_mode
        else: sys.stdout.write = getattr(self, mode + '_mode')

    def stderr(self, mode):
        
        if mode == 'standard': sys.stderr.write = self.standard_error_mode
        else: sys.stderr.write = getattr(self, mode + '_mode')


