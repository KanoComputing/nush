

        // NUSH 0.3 MAIN JS LIBRARY
        // This is Free Software (GPL)


var run = eval; // because ace will complain about eval
var time;

function ajax_request(method, url, async, data, handler) {

    // make an ajax request and return the response
    var request = new XMLHttpRequest();
    request.onreadystatechange = function() {

        if (request.readyState==4 && request.status==200) {
            request = request.response;
            }};

    request.open(method, url, async);
    if (data) request.send(data);
    else request.send();
    
    if (handler) handler(request);
    else return request;
    }


function enter(code, seen) {

    var data, index;

    // enter some code into the namespace
    if (seen === undefined) { seen = true }

    data = JSON.stringify({'code': code, 'seen': seen});
    ajax_request("POST", "/enter", true, data);

    // update the line history if this entry is to be seen
    if (seen && line_history) {
        index = line_history.indexOf(code);
        if (index !== -1) { line_history.splice(index, 1); }
        pointer = line_history.push(code);
        }}


function extend(extension, paths, redo) {

    // extend the interpreter's namespace with a list of paths
    ajax_request('POST', '/extend/'+extension+'/'+redo, true, JSON.stringify(paths));
    }


function superspace(update) {

    // update the superspace and return a copy of it
    // pass in no arg to just get a copy (no update)
    if (!update) { return ajax_request("GET", "/nush/builtin/superspace", false) }
    return ajax_request("POST", "/nush/builtin/superspace", false, JSON.stringify(update));
    }


function supereval(pin, value, pkg) {

    // evaluate the value arg, then update the superspace
    // using pin as a key (and the evaluation as its value)
    // this is typically called from the namespace
    var update = {};
    update[pin] = run(value);
    superspace(update);
    }

function radio_socket(channels) {

    // returns a websocket that will receive all messages on
    // channels (a string or array of strings)
    if (!$.isArray(channels)) { channels = [channels] }
    channels = channels.join('/');
    return new WebSocket('ws://localhost:10002/ws/' + channels);
    }


function Radio() {
    
    this.ws = new WebSocket('ws://localhost:10002/ws');
    channels = {};
    this.channels = channels;
    
    this.register = function(_channels, handler) {
        
        if (!$.isArray(_channels)) _channels = [_channels];
        
        _channels.forEach(function (channel) {

            if (!channels.hasOwnProperty(channel)) channels[channel] = [handler];
            else channels[channel].push(handler);
            });
        
        this.ws.send(JSON.stringify(channels));
        };
        
    this.send = function(channels, message) {
        
        var data = JSON.stringify([channels, message]);
        ajax_request('POST', '/nush/builtin/radio_send', true, data);
        };
    
    this.ws.onmessage = function(event) {
        
        var data = JSON.parse(event.data);
        var message = data.message;
        var channel = data.channel;
        channels[channel].forEach(function(handler) { handler(channel, message) }
        )};
    
    return this;
}

// get a unique pin
function issue_pin() { return ajax_request("GET", "/nush/builtin/issue_pin", false) }


function get_time() {

    // return the time and date as a pretty string
    var now   = new Date(),
        mins  = now.getMinutes(),
        hours = now.getHours(),
        date  = now.getDate(),
        day   = now.getDay(),
        month = now.getMonth(),
        time; // will be 'am' or 'pm'

    if (mins < 10) { mins = '0' + mins}

    if (hours > 12) { hours -= 12; time = 'pm' }
    else { time = 'am' }

    day   = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][day];
    month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month];

    return hours+':'+mins+time+' '+day+' '+date+' '+month;
    }
