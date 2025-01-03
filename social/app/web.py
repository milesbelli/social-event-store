from re import M
from flask import Flask, render_template, request, redirect, send_file, jsonify, url_for
import datetime
import pytz
import fitbit, common, twitter, foursquare, sms, psn
from multiprocessing import Process
import os

app = Flask(__name__)

# To make this work in Unix:
#   export FLASK_APP=web.py
#   flask run

# To make this work in Windows:
#   set FLASK_APP=web.py
#   flask run

# Can specify --host=0.0.0.0 to make available across LAN


@app.route("/")
def main():
    warning = "Database appears to be stopped. Start it before continuing." if not twitter.database_running() \
        else ""
    return render_template("main.html", warn=warning)


@app.route("/top")
def top():
    disable = request.args.get("disable", type=bool)    # This should be implied false
    return render_template("top.html", disable=disable)


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":

        maps_key = os.getenv("MAPS_KEY")

        user_prefs = common.UserPreferences(1)

        if request.args.get("term"):
            search_term = request.args.get("term")
            print(f"Searching for events containing '{search_term}'")
            # This is clumsy and won't scale... this twitter function should be moved to common and made scalable
            tweets = twitter.search_for_term(search_term, user_prefs)
            tweets = common.events_in_local_time(tweets, user_prefs, True)
            tweets = common.convert_dict_to_event_objs(tweets, user_prefs=user_prefs)

            # After setting up the calendar, reverse the order if user preferences is set.
            if user_prefs.reverse_order == 1:
                tweets = twitter.reverse_events(tweets)

            return render_template("search.html", events=tweets, default=search_term, count=len(tweets),
                                   prefs=user_prefs, maps=maps_key)

        else:
            return render_template("search.html", prefs=user_prefs,
                                   maps=maps_key)


@app.route("/calendar/<date>")
def calendar(date):
    date_format = datetime.datetime.strptime(date, "%Y-%m-%d").date()

    output_calendar = twitter.calendar_grid(date_format)

    next_dt = datetime.date(date_format.year, date_format.month, 28) + datetime.timedelta(7, 0)
    next_dt = datetime.date(next_dt.year, next_dt.month, 1)
    prev_dt = datetime.date(date_format.year, date_format.month, 1) - datetime.timedelta(1, 0)

    navigation = {"previous": prev_dt.strftime("%Y-%m-%d"),
                  "next": next_dt.strftime("%Y-%m-%d")}

    cal_header = date_format.strftime("%B %Y")

    print(output_calendar)

    return render_template("calendar.html", calendar=output_calendar, nav=navigation, header=cal_header, date=date)


@app.route("/viewer/<year>/<month>")
def viewer(year, month):

    maps_key = os.getenv("MAPS_KEY")

    user_prefs = common.UserPreferences(1)

    first_of_month = datetime.date(int(year), int(month), 1)

    month_of_events = common.get_one_month_of_events(int(year), int(month), preferences=user_prefs)
    output_calendar = twitter.calendar_grid(first_of_month, tweets=month_of_events)

    # After setting up the calendar, reverse the order if user preferences is set.
    if user_prefs.reverse_order == 1:
        month_of_events = twitter.reverse_events(month_of_events)

    # Quickly get next/previous months
    next_dt = datetime.date(first_of_month.year, first_of_month.month, 28) + datetime.timedelta(7, 0)
    next_dt = datetime.date(next_dt.year, next_dt.month, 1)
    prev_dt = datetime.date(first_of_month.year, first_of_month.month, 1) - datetime.timedelta(1, 0)

    navigation = {"previous": prev_dt.strftime("%Y/%m"),
                  "next": next_dt.strftime("%Y/%m")}

    cal_header = {"month": first_of_month.strftime("%B"),
                  "year": first_of_month.strftime("%Y")}

    pickers = twitter.build_date_pickers()

    date_values = {"year": year,
                   "month": month}

    return render_template("viewer.html", month=month_of_events, calendar=output_calendar,
                           header=cal_header, nav=navigation, pickers=pickers, date_values=date_values,
                           prefs=user_prefs, maps=maps_key)


@app.route("/viewer")
def viewer_select():
    month = request.args.get("month", type=int) or datetime.datetime.now().month
    year = request.args.get("year", type=int) or datetime.datetime.now().year

    return redirect(url_for("viewer", year=year, month=month))


@app.route("/filter", methods=["POST"])
def event_filter_viewer():

    user_id = 1

    preferences = common.UserPreferences(user_id)

    filter_prefs = dict()

    event_types = ["twitter", "fitbit-sleep", "foursquare", "sms", "psn"]

    for event_type in event_types:
        filter_prefs[f"show_{event_type}"] = 1 if request.form.get(f"show_{event_type}") else 0

    preferences.save_filters(**filter_prefs)

    return redirect(url_for(request.form.get("dest"), year=request.form.get("year"), month=request.form.get("month"),
                            term=request.form.get("search")))


@app.route("/upload", methods=["GET", "POST"])
def upload_data():

    if request.method == "GET":
        return render_template("upload.html")

    elif request.method == "POST":
        file = request.files["zipfile"]
        file_path = f"data/{file.filename}"
        destination_file = open(file_path, "wb")
        destination_file.write(file.read())
        if request.form["source"] == "twitter":
            file_proc_bkg = Process(target=twitter.process_from_file, args=(file_path,), daemon=True)
            file_proc_bkg.start()
        elif request.form["source"] == "fitbit-sleep":
            file_proc_bkg = Process(target=fitbit.process_from_file, args=(file_path,), daemon=True)
            file_proc_bkg.start()
        elif request.form["source"] == "foursquare":
            file_proc_bkg = Process(target=foursquare.process_from_file, args=(file_path,), daemon=True)
            file_proc_bkg.start()
        elif request.form["source"] == "sms":
            file_proc_bkg = Process(target=sms.process_from_file, args=(file_path,), daemon=True)
            file_proc_bkg.start()

        return render_template("upload.html", status_message=f"The file {file.filename} has been successfully uploaded.")


@app.route("/settings", methods=["GET", "POST"])
def user_settings():
    user_prefs = common.UserPreferences(1)

    if request.method == "GET":
        return render_template("settings.html", timezones=pytz.all_timezones, user_prefs=user_prefs)

    elif request.method == "POST":
        reverse_order = 1 if request.form.get('reverse_order') else 0
        print(f" reverse order is {reverse_order}")
        user_prefs.update(timezone=request.form.get('timezone'), reverse_order=reverse_order)
        print(f"Timezone is {request.form['timezone']}, saved successfully")
        save_message = "Changes saved successfully"

        return render_template("settings.html", timezones=pytz.all_timezones, user_prefs=user_prefs, msg=save_message)


@app.route("/export", methods=["GET", "POST"])
def export_ical():
    user_prefs = common.UserPreferences(1)

    if request.method == "GET":
        download = request.args.get("download")

        # The download argument indicates user clicked the download button
        if download:
            return send_file(download, as_attachment=True)

        # This is the default response the user should get upon first loading the Export page
        else:
            return render_template("export.html")

    elif request.method == "POST":
        source = request.form.get("source")
        start_date = request.form.get("start-date")
        end_date = request.form.get("end-date")

        if start_date and end_date:
            events = common.get_events_for_date_range(start_date, end_date, user_prefs, sources=[source])
            output_path = common.export_ical(events)

            return render_template("export.html", count=len(events), link=output_path, start=start_date, end=end_date)

        else:
            return render_template("export.html", message="You need to select a date range.")


@app.route("/edit-sleep/<sleep_id>", methods=["GET", "POST"])
def edit_sleep(sleep_id):
    fitbit_sleep_event = fitbit.FitbitSleepEvent(sleep_id)

    if request.method == "GET":

        return render_template("edit-sleep.html", event=fitbit_sleep_event, timezones=pytz.all_timezones)

    elif request.method == "POST":
        old_timezone = fitbit_sleep_event.timezone
        fitbit_sleep_event.update_timezone(request.form["timezone"])
        save_message = f"Timezone changed from {old_timezone} to {fitbit_sleep_event.timezone}."
        return render_template("edit-sleep.html", event=fitbit_sleep_event, timezones=pytz.all_timezones,
                               message=save_message)


@app.route("/get-status/<status_id>", methods=["GET"])
def get_twitter_status(status_id):
    user_id = 1
    user_prefs = common.UserPreferences(user_id)
    status = twitter.get_status_from_twitter(status_id, user_prefs)
    if status:
        return jsonify(status)


@app.route("/get-map/<source>/<source_id>", methods=["GET"])
def get_map(source, source_id):
    foursquare_api_id = os.getenv("FSQ_KEY")
    foursquare_api_secret = os.getenv("FSQ_SECRET")
    if source == "foursquare":
        venue = foursquare.get_venue_details(source_id, foursquare_api_id, foursquare_api_secret)
        return jsonify(venue)


@app.route("/edit-sms/<sms_id>", methods=["GET"])
def edit_sms(sms_id):
    return render_template("edit-sms.html")


@app.route("/conversation/<convo_id>", methods=["GET"])
def view_convo(convo_id):
    user_id = 1
    user_prefs = common.UserPreferences(user_id)

    start = request.args.get("start")

    size = int(request.args.get("size") or 50)

    messages, next, title = common.get_conversation_page(convo_id, size, start,
                                                  preferences=user_prefs)

    prev = common.get_previous_sms(convo_id, start, size, user_prefs)

    return render_template("conversation.html", days_list=messages, next=next,
                           prev=prev, size=size, conv_name=title)


@app.route("/fetch", methods=["GET", "POST"])
def fetch_from_api():
    if request.method == "GET":
        return render_template("api-fetch.html")

    elif request.method == "POST":
        psn_key = request.form.get("psnkey")
        user_prefs = common.UserPreferences(1)
        success = psn.api_fetch_background(user_prefs, psn_key)

        return render_template("api-fetch.html", status=success)


# Running this will launch the server
if __name__ == "__main__":
    app.run(host="0.0.0.0")
