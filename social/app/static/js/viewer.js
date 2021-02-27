window.onscroll = function() {update_date_header()};

function update_date_header() {
    // Get all IDs for all dates
    allDates = document.querySelectorAll("h2[id]:not(.date-header)");

    var i;
    var passedId;

    // Have to loop through each date header and figure out what we've just scrolled past, if any
    for (i = 0; i < allDates.length; i++) {
        thisDate = document.getElementById(allDates[i].id)
        scrollingPosition = document.documentElement.scrollTop

        // Check scrolling position against positions of dates in list
        if (scrollingPosition > (thisDate.offsetTop - 10)) {
            passedId = thisDate;
            document.getElementById("floating-date-header").style.display = 'block';
        } else if (i == 0){
            document.getElementById("floating-date-header").style.display = 'none';
            i = allDates.length;
        } else {
        i = allDates.length;
        }

        // Hide the date header if it's too close to the next date
        if ((i == allDates.length) && (scrollingPosition > (thisDate.offsetTop - 50))){
        document.getElementById("floating-date-header").style.display = 'none';
        }
    }

    // If there's something to show, update the header element
    if (passedId) {
        document.getElementById("floating-date-header").innerHTML = passedId.textContent;
    }

};

function show_hide_map(map_id) {
    if(document.getElementById(map_id).style.display=="none"){
        document.getElementById(map_id).style.display="block";
    }
    else {
        document.getElementById(map_id).style.display="none";
    }
}
function get_map(map_id, latitude, longitude) {
    console.log("#"+map_id)
    console.log(latitude+", "+longitude);

    if(document.getElementById(map_id).style.display=="none") {
        document.getElementById(map_id).style.display="block";

        if (window.innerWidth < 630) {
            document.getElementById(map_id).style.width = (window.innerWidth-30)+"px";
        }

        var map = new Microsoft.Maps.Map("#"+map_id, {
        center: new Microsoft.Maps.Location(latitude, longitude),
        zoom: 14
        });

        var center = map.getCenter();

        var pin = new Microsoft.Maps.Pushpin(center);

        map.entities.push(pin);
    }

    else {
        document.getElementById(map_id).style.display="none";
    }

};

function get_map_by_id(obj_id, source, source_id) {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var obj = JSON.parse(this.responseText);
            foot_id = obj_id + "_footer";
            document.getElementById(foot_id).innerHTML = obj["city"] + ", " + obj["state"] + ", " + obj["country"];
            map_id = obj_id + "_map";
            get_map(map_id, obj["latitude"], obj["longitude"]);
            button_id = obj_id + "_button";
//            document.getElementById(button_id).onclick = "get_map('" + map_id + "', " + obj["latitude"] + ", " + obj["longitude"] + ")"
            document.getElementById(button_id).onclick = function() {get_map(map_id, obj["latitude"], obj["longitude"]); };

        };
    };
    xhttp.open("GET", "/get-map/" + source + "/" + source_id, true);
    xhttp.send();
};

function fetch_reply(reply_id, status_id) {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var obj = JSON.parse(this.responseText)
            var user_name = ""
            if (obj["user"]["screen_name"]) {
            user_name = obj["user"]["screen_name"] + ": "}
            document.getElementById("reply_"+status_id).innerHTML = (user_name + obj["text"]);
            document.getElementById("reply_"+status_id).style.display = "block";
            document.getElementById("reply_btn_"+status_id).style.display = "none";
        };
    };
    console.log("Fetching status id: " + reply_id)
    xhttp.open("GET", "/get-status/" + reply_id, true);
    xhttp.send();
};