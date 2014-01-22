'''
nush config
===========

This file is executed immediately after the shell has finished loading. The code
in this file is executed as the very last step in the nush boot process. You can
use it to automate your nush setup, loading hacks and importing modules, setting
handlers, and so on. It defines your default space.

There's no special config system in nush. You just put code in this config file,
which can load other code. This hook allows you to personalise the way that nush
works when it starts up. You can reference all of nush's builtin stuff, like the
shell and finder, in the code that you enter here.

'''