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
        date = request.form['tweetday'] or datetime.datetime.today()
        print("Getting tweets for {}.".format(date))
        tweets = twitter.get_tweets_for_date_range(date, date)
        tweets = twitter.tweets_in_local_time(tweets, True)

        return render_template("day.html", events=tweets, default=date)
