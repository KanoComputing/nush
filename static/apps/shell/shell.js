

        // NUSH 0.1 CORE NAMESPACE
        // This is Free Software (GPL)


// -------- GLOBALS ----------------

var editor = ace.edit("editor"),                            // hook to the ace editor api
    ed = document.getElementById('editor'),                 // the chalkboard editor element
    favicon = document.getElementById('favicon'),           // the favicon element
    feeds = document.getElementById('feeds'),               // the output feeds element
    clock = document.getElementById('clock'),               // the entire main screen element
    lines = 1,                                              // tracks editor lines at last count
    line_history = [],                                      // the user's command line input history
    stdout = null,                                          // tracks the existance of droidspace feed
    pointer = 0,                                            // tracks place in history during scrolling
    cwd,                                                    // tracks the current working directory
    run = eval;                                             // stops ace from complaining that eval is evil



// -------- EDITOR SETUP ----------------

ed.style.fontSize ='12px';
ed.style.height = '16px';
editor.setTheme("ace/theme/vibrant_ink");
editor.getSession().setTabSize(4);
editor.getSession().setUseWrapMode(true);
editor.getSession().setUseSoftTabs(true);
editor.getSession().setMode('ace/mode/python');
editor.setHighlightActiveLine(false);
editor.setShowPrintMargin(false);
editor.setBehavioursEnabled(false);
editor.setDisplayIndentGuides(false);
editor.renderer.setShowGutter(false);
editor.focus()

editor.on('change', function () {

    // resize the editor whenever its content changes

    var nu_lines = editor.getValue().split('\n').length;
    if (nu_lines !== lines) { ed.style.height = (16 * nu_lines) + 'px'; lines = nu_lines }
    editor.resize();
    clock.scrollIntoView();
    });

// focus the editor whenever the escape key is pressed (outside the editor)
$(document).keydown(function(e){ if (e.keyCode == 27) { editor.focus(); return false } });


// -------- WEBSOCKET SETUP ----------------

!function connect() {

    // maintain a websocket connection and handle incoming packages

    var socket = radio_socket('pin0');

    socket.onopen = function() { extend('shell', ['/extensions/builtin/shell.py', '/extensions/shell.py'], false) };
    socket.onmessage = function(e) { pkg = JSON.parse(e.data); run(pkg.jscript) };
    socket.onclose = function() {

        connected(0);
        toastr.error('CONNECTION LOST')
        setTimeout(connect, 1400);

        };}();


function connected(state) {

    // updates the banner and favicon whenever the connection state changes

    var color;
    if (state === 0) { color = 'red' }
    else if (state == 1) { color = 'orange' }
    else { color = 'green' }

    favicon.href = '/static/apps/shell/'+color+'_favicon.png';
    document.getElementById('bannerhead').className = color;
    }


// -------- CLOCK SETUP ----------------

!function check_time(mins) {

    // recursively checks the time every 0.5 seconds until the current minute
    // changes, then it updates the clock using get_time from nush.js, then it
    // waits 59 seconds before starting again

    var nu_mins = new Date().getMinutes();

    if (nu_mins !== mins) {

        mins = nu_mins;
        clock.innerHTML = get_time();
        setTimeout(check_time, 59000, mins);
        }

    else { setTimeout(check_time, 500, mins) }

    }(new Date().getMinutes());



// -------- MANAGE DROIDSPACE OUTPUT ----------------

function create_feed(feed, id) {

    // append a new feed to the feeds

    var child = document.createElement('div');
    child.className = 'feed';
    child.innerHTML = feed;
    if (id) { child.id = id }
    feeds.appendChild(child);
    clock.scrollIntoView();
    }


function append_to_feed(feed, string) {

    // append some output to a feed

    var child = document.createElement('span');
    child.innerHTML = string;
    feed.appendChild(child);
    clock.scrollIntoView();
    }


function output(string) {

    // handle any output from the user's interpreter

    if (stdout === null) {
        var stdout_feed = '<good>nush</good> <lite>#</lite> interpreter';
        create_feed(stdout_feed, 'stdout');
        stdout = document.getElementById('stdout');
        }

    feeds.appendChild(stdout);
    append_to_feed(stdout, string);
    }


function submit_stdin(element, content) {
    
    var update = {};
    update[element.id] = content;
    superspace(update);
    
    $(element).replaceWith(
        '<lite><was-good>' + element.innerText + '</was-good><xmp style=display:inline>' + content + '</xmp><xmp></xmp></lite>'
        );}

// clear all feeds from the screen
function clear_feeds() { feeds.innerHTML = null; stdout = null }


// -------- HANDY WRAPPERS ----------------

function toast_extension(extension) { toastr.success('NAMESPACE EXTENDED: ' + extension) }
function license() { enter('shell.license()', false) }
function fail_save() { toastr.error('FAIL: You can\'t save the shell.') }



// -------- KEYBINDINGS ----------------

// Meta + S: save content
editor.commands.addCommand({

    name: 'fail_save',
    bindKey: {win: 'Ctrl-s',  mac: 'Cmd-s'},
    exec: function(editor) { fail_save(); }
    });

// Enter: execute the content if it's a command, else create a new line
editor.commands.addCommand({

    name: 'handle_enter',
    bindKey: {win: 'Enter',  mac: 'Enter'},
    exec: function(editor) {

        var content = editor.getValue();

        if (content === '.') { editor.setValue(''); clear_feeds() }
        else if (content.indexOf('.') === 0) { enter(content); editor.setValue('') }
        else { editor.insert('\n') }
        }});

// Meta + Enter: execute the content, no matter what
editor.commands.addCommand({

    name: 'handle_meta_enter',
    bindKey: {win: 'Ctrl-Enter',  mac: 'Cmd-Enter'},
    exec: function(editor) {

        enter(editor.getValue());
        editor.setValue('');
        ed.style.height = '16px';
        }});

// Meta + Up: scroll back through line history
editor.commands.addCommand({

    name: 'rewind_history',
    bindKey: {win: 'Ctrl-Up',  mac: 'Cmd-Up'},
    exec: function(editor) {

        pointer -= 1;

        if (pointer >= 0) { editor.setValue(line_history[pointer]) }
        else { editor.setValue(''); pointer = -1 }

        editor.clearSelection(1);
        editor.resize();
        clock.scrollIntoView();
        }});


// Meta + Down: scroll back through line history
editor.commands.addCommand({

    name: 'forward_history',
    bindKey: {win: 'Ctrl-Down',  mac: 'Cmd-Down'},
    exec: function(editor) {

        pointer += 1;

        if (pointer < line_history.length) { editor.setValue(line_history[pointer]) }
        else { editor.setValue(''); pointer = line_history.length }

        editor.clearSelection(1);
        editor.resize();
        clock.scrollIntoView();
        }});



// -------- ONLOAD ----------------

clock.innerText = get_time();