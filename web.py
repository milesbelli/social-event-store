from flask import Flask, render_template, request, redirect, send_file
import twitter
import datetime
import pytz
from multiprocessing import Process

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


@app.route("/tweet/<tweetid>")
def one_tweet(tweetid=None):
    tweet = twitter.get_one_tweet(tweetid)

    return render_template("tweet.html", events=tweet)


@app.route("/day", methods=["GET", "POST"])
def one_day():
    if request.method == "GET":

        return render_template("day.html")

    elif request.method == "POST":
        user_prefs = twitter.UserPreferences(1)
        date = request.form['tweetday'] or datetime.datetime.today().strftime("%Y-%m-%d")
        print("Getting tweets for {}.".format(date))
        tweets = twitter.get_tweets_for_date_range(date, date)
        tweets = twitter.tweets_in_local_time(tweets, user_prefs, True)

        return render_template("day.html", events=tweets, default=date)


@app.route("/day/<date>", methods=["GET"])
def one_day_from_url(date):
    user_pref = twitter.UserPreferences(1)
    print("Getting tweets for {}.".format(date))
    tweets = twitter.get_tweets_for_date_range(date, date)
    tweets = twitter.tweets_in_local_time(tweets, user_pref, True)

    return render_template("day.html", events=tweets, default=date)


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":

        return render_template("search.html")

    elif request.method == "POST":
        user_prefs = twitter.UserPreferences(1)
        search_term = request.form["search"]
        print("Searching for tweets containing '{}'".format(search_term))
        tweets = twitter.search_for_term(search_term)
        tweets = twitter.tweets_in_local_time(tweets, user_prefs, True)

        # After setting up the calendar, reverse the order if user preferences is set.
        if user_prefs.reverse_order == 1:
            tweets = twitter.reverse_events(tweets)

        return render_template("search.html", events=tweets, default=search_term, count=len(tweets))


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

    user_prefs = twitter.UserPreferences(1)

    first_of_month = datetime.date(int(year), int(month), 1)

    month_of_events = twitter.get_one_month_of_events(int(year), int(month), preferences=user_prefs)
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

    return render_template("viewer.html", month=month_of_events, calendar=output_calendar,
                           header=cal_header, nav=navigation, pickers=pickers)


@app.route("/viewer")
def viewer_select():
    month = request.args.get("month", type=int) or datetime.datetime.now().month
    year = request.args.get("year", type=int) or datetime.datetime.now().year

    return redirect(f"/viewer/{year}/{month}")


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

        return render_template("upload.html", status_message=f"The file {file.filename} has been successfully uploaded.")


@app.route("/settings", methods=["GET", "POST"])
def user_settings():
    user_prefs = twitter.UserPreferences(1)

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
    user_prefs = twitter.UserPreferences(1)

    if request.method == "GET":
        download = request.args.get("download")

        # The download argument indicates user clicked the download button
        if download:
            return send_file(download, as_attachment=True)

        # This is the default response the user should get upon first loading the Export page
        else:
            return render_template("export.html")

    elif request.method == "POST":
        start_date = request.form.get("start-date")
        end_date = request.form.get("end-date")

        if start_date and end_date:
            tweets = twitter.get_tweets_for_date_range(start_date, end_date, user_prefs)
            output_path = twitter.export_ical(tweets)

            return render_template("export.html", count=len(tweets), link=output_path, start=start_date, end=end_date)

        else:
            return render_template("export.html", message="You need to select a date range.")


# Running this will launch the server
if __name__ == "__main__":
    app.run(host="0.0.0.0")
