

        # NUSH 0.1 SHELL EXTENSION
        # This is Free Software (GPL)


try: shell.execute('connected(2)')
except NameError:

    from nush import goto, edit, view, mark, Shell

    nush.shell = Shell()

    shell = nush.shell
    input = shell.prompt
    pipes = nush.pipes.Pipework(nush.radio)
    stdout_mode = pipes.stdout_mode
    stderr_mode = pipes.stderr_mode

    shell.execute('connected(1)')

    hook = ROOTDIR + '/extensions/shell.py'
    if os.path.isfile(hook): exec(compile(open(hook).read(), hook, 'exec'))

    del hook, Shell, pipes

    shell.execute('connected(2)')