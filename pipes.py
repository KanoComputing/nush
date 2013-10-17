

        # NUSH 0.1 PIPES AND BUFFER
        # This is Free Software (GPL)


import sys
import cgi
import json

from time import sleep
from threading import Thread



class PostMaster(object):

    '''Handles a string buffer, pushing stdout and stderr to Chrome.'''

    def __init__(self, radio):

        self.string = ''
        flusher = Thread(target=self.flush, args=(radio, ))
        flusher.daemon = True
        flusher.start()

    def flush(self, radio):

        while True:

            sleep(0.005)
            if not self.string: continue
            string, self.string = self.string, ''
            radio.send('pin0', json.dumps({'jscript': 'output(pkg.string)', 'string': string}))



class Pipe(object):

    '''Base class for all pipes.'''

    def __init__(self, postmaster): self.postmaster = postmaster


class PythonStyle(Pipe):

    '''Escapes output so it looks like it would in a terminal.'''

    def write(self, string):

        string = '<xmp style=display:inline>{0}</xmp>'.format(string)
        self.postmaster.string += string


class PrettyPrint(Pipe):

    '''Preserves newlines in output, but otherwise prints HTML.'''

    def write(self, string):

        string = string.replace('\n', '<br>')
        self.postmaster.string += string


class PrettyError(Pipe):

    '''Escapes output so it looks like it would in a terminal, but
    italicised and coloured red.
    '''

    def write(self, string):

        string = '<i class=red><xmp>{0}</xmp></i>'.format(string)
        self.postmaster.string += string



class Pipework(object):

    def __init__(self, radio):

        while 'pin0' not in radio.channels: pass

        self.pipes = (PythonStyle, PrettyPrint, PrettyError)
        self.postmaster = PostMaster(radio)
        sys.stdout = PrettyPrint(self.postmaster)
        sys.stderr = PrettyError(self.postmaster)

    def stdout_mode(self, mode): sys.stdout = self.pipes[mode](self.postmaster)

    def stderr_mode(self, mode): sys.stderr = self.pipes[mode](self.postmaster)
