

        // NUSH 0.3 SHELL
        // This is Free Software (GPL)


// -------- GLOBALS ----------------

var editor = ace.edit('editor'),                        // hook to the ace editor api
    ed = document.getElementById('editor'),             // the chalkboard editor element
    favicon = document.getElementById('favicon'),       // the favicon element
    feeds = document.getElementById('feeds'),           // the output feeds element
    clock = document.getElementById('clock'),           // the entire main screen element
    completer = document.getElementById('completer'),   // the completion dialog widget
    completing = false,                                 // tracks if the completer is visible
    lines = 1,                                          // tracks editor lines at last count
    line_history = [],                                  // the user's command line input history
    stdout = null,                                      // tracks the existance of droidspace feed
    pointer = 0,                                        // tracks place in history during scrolling
    prompt_count,                                       // tracks the number of pending stdin prompts
    cwd,                                                // tracks the current working directory
    run = eval;                                         // stops ace from complaining that eval is evil


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
editor.focus();

editor.on('change', function () {

    var content = editor.getValue();
    
    // set the context depending on the content
    if (content.indexOf('.') === 0) { editor.getSession().setMode(null); hide_completer() }
    else { editor.getSession().setMode('ace/mode/python') }
    
    // resize the editor whenever its content changes
    var nu_lines = content.split('\n').length;
    if (nu_lines !== lines) {
        ed.style.height = (16 * nu_lines) + 'px'; lines = nu_lines; editor.resize();
        }
    
    clock.scrollIntoView();
    
    if (completing) { setTimeout(complete, 30) }
    });

editor.getSelection().on('changeCursor', function() {
    
    if (completing) { setTimeout(complete, 30) }
    })


// -------- WEBSOCKET SETUP ----------------

!function connect() {

    // maintain a websocket connection and handle incoming packages

    var socket = radio_socket('pin0');

    socket.onopen = function() { extend('shell', ['/extensions/builtin/shell.py', '/extensions/shell.py'], false) };
    socket.onmessage = function(e) { pkg = JSON.parse(e.data); run(pkg.jscript) };
    socket.onclose = function() {

        connected(0);
        toastr.error('CONNECTION LOST');
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


clock.innerText = get_time();



// -------- MANAGE IO ----------------

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
    update_prompts();
    }


function clear_feeds() {
    
    // clear all feeds from the screen (so it looks like new)
    
    var cleared = clear_stdins();
    feeds.innerHTML = null;
    stdout = null;
    update_prompts();
    if (cleared) {
        var singular = ' prompt';
        if (cleared > 1) { singular += 's' }
        output('<br><br><meh>> Pending Prompts Destroyed (the string "quit" was returned for '+cleared+singular+').</meh><br>');
        }}


function submit_stdin(element, content) {
    
    // send the input for a given stdin prompt and replace with a ghosty
   
    var update = {};
    update[element.id] = content;
    superspace(update);
    
    $(element).replaceWith(
        '<lite><span class=pea><xmp style=display:inline>'
        + element.innerText + '</xmp></span><xmp style=display:inline>'
        + content + '</xmp></lite><br>'
        );
    
    editor.focus();
    update_prompts();
    }


function clear_stdins() {
    
    // return 'quit' as input to any stdin prompts destroyed
    
    var cleared = 0;
    
    $('form').each( function () {

        update ={};
        update[this.id] = 'quit';
        superspace(update);
        cleared++;
        });
    
    return cleared;
    }

function update_prompts() {
    
    // update the prompt counter, removing it if there are no prompts 
    
    if ($('.stdin_prompt').length) {
        $('#prompt_count').html(
            '<lite>* pending prompts </lite><span class=pea>' + $('.stdin_prompt').length + '</span>');
            }
    else { $('#prompt_count').html('&nbsp;') }
    
    clock.scrollIntoView();
    }

// clean up stdin prompts before leaving the page
window.onbeforeunload = function() { clear_stdins() };


// -------- COMPLETION STUFF ----------------

function complete(){
    
    // opens the completer (if not already open), then does one
    // completion (each time this is called)
    
    var completions = get_completions();
    if (!completions) { return false }
    completing = true;
    
    var place = $('.ace_cursor')[0].getBoundingClientRect();
    var style = {
        display: 'block',
        top: place.top + 16,
        left: place.left,
        bottom: 4
        };
        
    $(completer).css(style).html(JSON.parse(completions));
    }


function get_completions() {
    
    // get and return completions for the slate
    
    var cursor = editor.getCursorPosition();
    var content = editor.getValue();
    
    var data = JSON.stringify({
        'line': cursor.row + 1, 'index': cursor.column, 'content': content
        });

    return ajax_request('POST', '/nush/builtin/complete', false, data);
    }


function hide_completer() {
    
    // hide the completer from view
    
    completer.style.display = 'none';
    completing = false;
    }


window.onscroll = function() {
    
    // if the completer is visible it should follow the cursor
    
    if (!completing) { return false }
    
    var place = $('.ace_cursor')[0].getBoundingClientRect();
    var style = {
        top: place.top + 16,
        left: place.left,
        bottom: 4
        };

    $(completer).css(style);
    };


// TODO // .print <img src=http://imgs.xkcd.com/comics/python.png style=padding:12px>


function toast_extension(extension) { toastr.success('NAMESPACE EXTENDED: ' + extension) }
function license() { enter('shell.license()', false) }


// -------- KEYBINDINGS ----------------

// Ctrl + Dot (outside editor): highlight editor
$(window).bind('keydown', function(event) {
    if ( (event.ctrlKey || event.metaKey) && event.which == 190 && editor.isFocused() === false ) { editor.focus() }
    });

// Enter: execute the content if it's a command, else create a new line
editor.commands.addCommand({

    name: 'handle_enter',
    bindKey: {win: 'Enter',  mac: 'Enter'},
    passEvent: true,
    exec: function(editor) {

        var content = editor.getValue();

        if (content === '.') { editor.setValue(''); clear_feeds() }
        else if (content.indexOf('.') === 0) { enter(content); editor.setValue('') }
        else { editor.insert('\n') }
        }});

// Meta + Dot: do completion
editor.commands.addCommand({

    name: 'complete',
    bindKey: {win: 'Ctrl-.',  mac: 'Cmd-.'},
    exec: function(editor) {
        
        if (completing) { completer.style.display = 'none'; completing = false }
        else { completing = true; complete() }
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
    