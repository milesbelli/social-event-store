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
    return output


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

        return render_template("search.html", events=tweets, default=search_term)