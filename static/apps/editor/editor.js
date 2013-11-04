
        // NUSH: EDITOR SCRIPT

var lang = document.getElementById('lang').innerHTML,
    filepath = document.getElementById('filepath').innerHTML,
    appdir = document.getElementById('appdir').innerHTML,
    filename = filepath.split('/').pop(),
    favicon = document.getElementById('favicon'),
    editor = ace.edit("editor");

// ace editor configuration
editor.setTheme("ace/theme/vibrant_ink");
editor.getSession().setTabSize(4);
editor.getSession().setUseWrapMode(true);
editor.getSession().setUseSoftTabs(true);
editor.getSession().setMode('ace/mode/'+lang);
editor.setHighlightActiveLine(false);
editor.setShowPrintMargin(false);
editor.setBehavioursEnabled(false);
editor.setDisplayIndentGuides(false);
document.getElementById('editor').style.fontSize='12px';

// load the editor content into the editor (after load, so html is not rendered)
var timestamp = new Date().getTime(); // and stop chrome caching the f***ing response
var path = "/nush/builtin/load_file?path=" + filepath + "&timestamp=" + timestamp
editor.setValue(ajax_request("GET", path, false));
toastr.success( 'LOADED: ' + filename);

// get the cursor in the right place!
editor.clearSelection(1); editor.gotoLine(1);
editor.getSession().setScrollTop(1); editor.blur(); editor.focus();

// handler for turning the favicon red when editor content is changed
editor.getSession().on('change', function(e) { favicon.href = appdir + '/unsaved.png' });

// Meta + S: save content
editor.commands.addCommand({

    name: 'save',
    bindKey: {win: 'Ctrl-s',  mac: 'Cmd-s'},
    exec: function(editor) {

        var data = JSON.stringify({'content': editor.getValue(), 'path': filepath});
        var res = ajax_request("POST", "/save_file", false, data);
        favicon.href = appdir + '/saved.png';
        toastr.success('SAVED: ' + filename);
        }})
