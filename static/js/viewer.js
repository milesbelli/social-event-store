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
        if (scrollingPosition > (thisDate.offsetTop - 10)) {
            passedId = thisDate;
            document.getElementById("floating-date-header").style.display = 'block';
        } else if (i == 0) {
            document.getElementById("floating-date-header").style.display = 'none';
            i = allDates.length;
        } else {
            i = allDates.length;
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

}