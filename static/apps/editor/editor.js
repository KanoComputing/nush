
        // NUSH: EDITOR SCRIPT

var filepath = document.getElementById('filepath').innerHTML,
    filename = filepath.split('/').pop(),
    favicon = document.getElementById('favicon'),
    editor = ace.edit("editor"),
    mode = ace.require('ace/ext/modelist').getModeForPath(filepath).mode;

// ace editor configuration
editor.session.setMode(mode);
editor.setTheme("ace/theme/vibrant_ink");
editor.getSession().setTabSize(4);
editor.setShowPrintMargin(false);
editor.setBehavioursEnabled(false);
editor.setHighlightActiveLine(false);
editor.setDisplayIndentGuides(false);
editor.getSession().setUseWrapMode(true);
editor.getSession().setUseSoftTabs(true);
document.getElementById('editor').style.fontSize='12px';

// set the title to the filename
document.title = filepath.split('/').pop();

// load the editor content into the editor (after load, so html is not rendered)
var timestamp = new Date().getTime(); // and stop chrome caching the f***ing response
var path = "/nush/builtin/load_file?path=" + filepath + "&timestamp=" + timestamp;
editor.setValue(ajax_request("GET", path, false));
toastr.success( 'LOADED: ' + filename);

// get the cursor in the right place!
editor.clearSelection(1); editor.gotoLine(1);
editor.getSession().setScrollTop(1); editor.blur(); editor.focus();

// handler for turning the favicon red when editor content is changed
editor.getSession().on('change', function() { favicon.href = '/static/apps/editor/unsaved.png' });

// Meta + S: save content
editor.commands.addCommand({

    name: 'save',
    bindKey: {win: 'Ctrl-s',  mac: 'Cmd-s'},
    exec: function(editor) {

        var data = JSON.stringify({'content': editor.getValue(), 'path': filepath});
        var result = ajax_request("POST", "/save_file", false, data);
        
        if (result == 'success') {
            
            favicon.href = '/static/apps/editor/saved.png';
            toastr.success('SAVED: ' + filename);
            }
            
        else if (result == 'io_fail') toastr.error('IOError: ' + filename);

    }});