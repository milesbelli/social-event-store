from flask import Flask, render_template, request
import twitter
import datetime

app = Flask(__name__)

# To make this work in Unix:
#   export FLASK_APP=web.py
#   flask run

# To make this work in Windows:
#   set FLASK_APP=web.py
#   flask run


@app.route("/")
def hello_world():
    output = str(twitter.get_one_tweet(983216871)[0][4])
    today = datetime.date.today().strftime("%Y-%m-%d")
    return render_template("top.html", today=today)


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

    next_dt = datetime.datetime.strptime(output_calendar[-1][-1]["full_date"], "%Y-%m-%d") + datetime.timedelta(1,0)
    prev_dt = datetime.datetime.strptime(output_calendar[0][0]["full_date"], "%Y-%m-%d") - datetime.timedelta(1,0)

    navigation = {"previous": prev_dt.strftime("%Y-%m-%d"),
                  "next": next_dt.strftime("%Y-%m-%d")}

    months = {1: "January",
              2: "February",
              3: "March",
              4: "April",
              5: "May",
              6: "June",
              7: "July",
              8: "August",
              9: "September",
              10: "October",
              11: "November",
              12: "December"}

    cal_header = "{} {}".format(months[date_format.month], date_format.strftime("%Y"))

    return render_template("calendar.html", calendar=output_calendar, nav=navigation, header=cal_header)
