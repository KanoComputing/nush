
        // NUSH: SHELL

// -------- GLOBALS ----------------

var editor = ace.edit('editor'),                        // hook to the ace editor api
    ed = document.getElementById('editor'),             // the slate element
    doc = editor.getSession().getDocument(),            // the document being edited
    favicon = document.getElementById('favicon'),       // the favicon element
    feeds = document.getElementById('feeds'),           // the output feeds element
    clock = document.getElementById('clock'),           // the clock element
    stash = '',                                         // tracks the slate content when winding history
    stdout = null,                                      // tracks the existance of the interpreter feed
    prompt_count,                                       // tracks the number of pending stdin prompts
    cwd,                                                // tracks the current working directory
    run = eval;                                         // stops ace from complaining that eval is evil

// the input history and a pointer that's used to track the position when winding
var line_history = JSON.parse(ajax_request('GET', '/line_history', false));
var pointer = line_history.length;


// -------- EDITOR SETUP ----------------

ed.style.fontSize ='12px';
ed.style.height = '16px';
editor.setTheme("ace/theme/vibrant_ink");
editor.getSession().setTabSize(4);
editor.getSession().setUseWrapMode(false);
editor.getSession().setUseSoftTabs(true);
editor.getSession().setMode('ace/mode/python');
editor.setHighlightActiveLine(false);
editor.setShowPrintMargin(false);
editor.setBehavioursEnabled(false);
editor.setDisplayIndentGuides(false);
editor.renderer.setShowGutter(false);
editor.focus();

editor.on('change', function () {

    // resize the editor to fit the content, then scroll it into view
    
    ed.style.height = 16 * doc.getLength() + 'px';
    editor.resize();
    clock.scrollIntoView();

    // set the context depending on the content
    
    var content = editor.getValue();
        
    if (content.indexOf('.') === 0) {
        editor.getSession().setMode(null);
        return false;
        }
    
    editor.getSession().setMode('ace/mode/python');
    });


// -------- WEBSOCKET SETUP ----------------

!function connect() {

    // maintain a websocket connection and handle incoming packages

    var socket = radio_socket('pin0');

    socket.onopen = function() { extend('shell', ['/extensions/builtin/shell.py', '/extensions/shell.py'], false) };
    socket.onmessage = function(event) {

        pkg = JSON.parse(JSON.parse(event.data).message);
        run(pkg.jscript);
        };
    
    socket.onclose = function() {

        connected(0);
        toastr.error('CONNECTION LOST');
        setTimeout(connect, 1400);

        };}();


function connected(state) {

    // updates the banner and favicon whenever the connection state changes

    var color;
    if (state === 0)     color = 'red';
    else if (state === 1) color = 'orange';
    else color = 'green';

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
    if (id) child.id = id;
    feeds.appendChild(child);
    clock.scrollIntoView();
    }


function append_to_feed(feed, string) {

    // append some output to a feed

    var child = document.createElement('span');
    child.innerHTML = string;
    child.className = 'stdout';
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
        output('<meh><xmp>> Pending Prompts Destroyed (the string "quit" was returned for '+cleared+singular+').</xmp></meh>');
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
            '<yell>*</yell> <lite>pending prompts</lite> <norm>' + $('.stdin_prompt').length + '</norm>');
            }
            
    else { $('#prompt_count').html('&nbsp;') }
    
    clock.scrollIntoView();
    }

// clean up stdin prompts before leaving the page
window.onbeforeunload = function() { clear_stdins() };


// -------- MISC STUFF ----------------

function toast_extension(extension) { toastr.success('NAMESPACE EXTENDED: ' + extension) }
function license() { enter('shell.license()', false) }
// TODO MAYBE // .print <img src=http://imgs.xkcd.com/comics/python.png style=padding:12px>


// -------- SLATE KEYBINDINGS ----------------

editor.commands.addCommand({

    // clear screen    
    name: 'clear screen',
    bindKey: {win: 'Esc',  mac: 'Esc'},
    exec: function(editor) { clear_feeds() }});

editor.commands.addCommand({

    // Enter: execute the content if it's a command, else create a new line
    name: 'handle_enter',
    bindKey: {win: 'Enter',  mac: 'Enter'},
    passEvent: true,
    exec: function(editor) {

        var content = editor.getValue();

        if (content.indexOf('.') === 0) {
            enter(content);
            editor.setValue('');
            }
        else { return false }
        }});

editor.commands.addCommand({

    // Meta + Enter: execute the content, no matter what
    name: 'handle_meta_enter',
    bindKey: {win: 'Ctrl-Enter',  mac: 'Cmd-Enter'},
    exec: function(editor) {

        enter(editor.getValue());
        editor.setValue('');
        ed.style.height = '16px';
        }});

editor.commands.addCommand({

    // Meta + Up: scroll back through line history
    name: 'rewind_history',
    bindKey: {win: 'Ctrl-Up',  mac: 'Cmd-Up'},
    exec: function(editor) {

        var content = editor.getValue();
        
        if (pointer >= 0 && content != line_history[pointer]) {
            stash = content;
            pointer = line_history.length;
            }

        pointer -= 1;
        
        if (pointer >= 0) { editor.setValue(line_history[pointer]) }
        else { editor.setValue('# THE END OF HISTORY'); pointer = -1 }

        editor.clearSelection(1);
        clock.scrollIntoView();
        }});

editor.commands.addCommand({

    // Meta + Down: scroll forward through line history
    name: 'forward_history',
    bindKey: {win: 'Ctrl-Down',  mac: 'Cmd-Down'},
    exec: function(editor) {

        var content = editor.getValue();

        if (pointer != -1 && content != line_history[pointer]) {
            stash = content;
            pointer = line_history.length;
            }

        pointer += 1;

        if (pointer < line_history.length) { editor.setValue(line_history[pointer]) }
        else { editor.setValue(stash) }

        editor.clearSelection(1);     
        clock.scrollIntoView();
        }});


// -------- UNFOCUSSED SLATE KEYBINDINGS ----------------

$(window).bind('keydown', function(event) {
    
    // Meta + Dot: focus the editor
    if ( (event.ctrlKey || event.metaKey) && event.which == 190 && editor.isFocused() === false ) { editor.focus() }
    });
