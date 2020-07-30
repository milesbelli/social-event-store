from flask import Flask, render_template, request, redirect
import twitter
import datetime
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
    return render_template("top.html")


@app.route("/tweet/<tweetid>")
def one_tweet(tweetid=None):
    tweet = twitter.get_one_tweet(tweetid)

    return render_template("tweet.html", events=tweet)


@app.route("/day", methods=["GET", "POST"])
def one_day():
    if request.method == "GET":

        return render_template("day.html")

    elif request.method == "POST":
        date = request.form['tweetday'] or datetime.datetime.today().strftime("%Y-%m-%d")
        print("Getting tweets for {}.".format(date))
        tweets = twitter.get_tweets_for_date_range(date, date)
        tweets = twitter.tweets_in_local_time(tweets, True)

        return render_template("day.html", events=tweets, default=date)


@app.route("/day/<date>", methods=["GET"])
def one_day_from_url(date):
    print("Getting tweets for {}.".format(date))
    tweets = twitter.get_tweets_for_date_range(date, date)
    tweets = twitter.tweets_in_local_time(tweets, True)

    return render_template("day.html", events=tweets, default=date)


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":

        return render_template("search.html")

    elif request.method == "POST":
        search_term = request.form["search"]
        print("Searching for tweets containing '{}'".format(search_term))
        tweets = twitter.search_for_term(search_term)
        tweets = twitter.tweets_in_local_time(tweets, True)

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

    first_of_month = datetime.date(int(year), int(month), 1)

    month_of_events = twitter.get_one_month_of_events(int(year), int(month))
    output_calendar = twitter.calendar_grid(first_of_month, tweets=month_of_events)

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


# Running this should launch the server, but it doesn't seem to work in Unix
if __name__ == "__main__":
    app.run(host="0.0.0.0")
