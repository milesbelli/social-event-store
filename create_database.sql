CREATE USER IF NOT EXISTS 'socialuser'@'localhost' IDENTIFIED BY 'resetme';
CREATE USER IF NOT EXISTS 'socialadmin'@'localhost' IDENTIFIED BY 'Abc@123';

CREATE DATABASE IF NOT EXISTS social
CHARACTER SET utf8mb4
COLLATE utf8mb4_general_ci;

GRANT SELECT, INSERT, UPDATE ON social.* TO 'socialuser'@'%';
GRANT ALL PRIVILEGES ON social.* TO 'socialadmin'@'localhost' WITH GRANT OPTION;

USE social;

CREATE TABLE IF NOT EXISTS events (
eventid INT(11) NOT NULL AUTO_INCREMENT,
userid INT(11) NOT NULL,
eventdate DATE NOT NULL,
eventtime TIME,
eventtype VARCHAR(16) NOT NULL,
detailid BIGINT(20),
PRIMARY KEY(eventid));

CREATE TABLE IF NOT EXISTS tweetdetails (
tweetid BIGINT(20) NOT NULL,
userid INT(11) NOT NULL,
tweettext TEXT,
twitteruserid INT(11),
latitude DOUBLE(10,8),
longitude DOUBLE(11,8),
replyid BIGINT(20),
client VARCHAR(255),
retweetid BIGINT(20),
PRIMARY KEY(tweetid));

CREATE TABLE IF NOT EXISTS tweetmedia (
tweetid BIGINT(20) NOT NULL,
mediaurl VARCHAR(100) NOT NULL,
PRIMARY KEY(tweetid,mediaurl));

CREATE TABLE IF NOT EXISTS tweethashtags (
tweetid BIGINT(20) NOT NULL,
ixstart INT(3) NOT NULL,
hashtag VARCHAR(280) NOT NULL,
PRIMARY KEY(tweetid,ixstart));

CREATE TABLE IF NOT EXISTS retweetdetails (
tweetid BIGINT(20) NOT NULL,
userid INT(11) NOT NULL,
usernm VARCHAR(255) NOT NULL,
replyid BIGINT(20),
client VARCHAR(255),
tweetdate DATE,
tweettime TIME);

CREATE TABLE IF NOT EXISTS tweetconflicts (
tweetid BIGINT(20) NOT NULL,
field VARCHAR(20) NOT NULL,
metadata VARCHAR(280),
PRIMARY KEY(tweetid, field, metadata));

CREATE TABLE IF NOT EXISTS tweeturls (
tweetid BIGINT(20) NOT NULL,
shorturl VARCHAR(280),
displayurl VARCHAR(280),
ixstart INT(3),
ixstop INT(3),
PRIMARY KEY(tweetid, ixstart));

CREATE TABLE IF NOT EXISTS user_preference (
userid INT(11) NOT NULL,
preference_key VARCHAR(64) NOT NULL,
preference_value VARCHAR(128) NOT NULL,
PRIMARY KEY(userid, preference_key));

CREATE TABLE IF NOT EXISTS fitbit_sleep (
sleepid BIGINT(15) NOT NULL AUTO_INCREMENT,
userid INT(11) NOT NULL,
logid BIGINT(15) NOT NULL,
startdatetime DATETIME NOT NULL,
enddatetime DATETIME NOT NULL,
timezone VARCHAR(40) NOT NULL,
duration INT(8),
mainsleep INT(1),
PRIMARY KEY(sleepid));

CREATE TABLE IF NOT EXISTS fitbit_sleep_stages (
sleepid BIGINT(15) NOT NULL,
sleepstage VARCHAR(16) NOT NULL,
stagecount INT(5),
stageminutes INT(4),
avgstageminutes INT(4),
PRIMARY KEY(sleepid, sleepstage));

CREATE TABLE IF NOT EXISTS fitbit_sleep_data (
sleepid BIGINT(15) NOT NULL,
sleepdatetime DATETIME NOT NULL,
sleepstage VARCHAR(16),
seconds INT(5),
PRIMARY KEY(sleepid, sleepdatetime));

CREATE TABLE IF NOT EXISTS tweet_in_reply (
tweetid BIGINT(20) NOT NULL,
createdate DATETIME,
username VARCHAR(16),
userid BIGINT(20),
inreplytouser BIGINT(20),
inreplytoid BIGINT(20),
statustext VARCHAR(280),
lang VARCHAR(4),
PRIMARY KEY(tweetid));

CREATE TABLE IF NOT EXISTS foursquare_checkins (
eventid BIGINT(15) NOT NULL AUTO_INCREMENT,
checkinid VARCHAR(32) NOT NULL,
eventtype VARCHAR(16),
tzoffset INT(4) NOT NULL,
venueid VARCHAR(32) NOT NULL,
venuename VARCHAR(200),
checkintime INT(11),
shout VARCHAR(140),
veventid VARCHAR(32),
veventname VARCHAR(200),
primarycatid VARCHAR(32),
primarycatname VARCHAR(32),
PRIMARY KEY (eventid),
UNIQUE KEY (checkinid)
);

CREATE TABLE IF NOT EXISTS foursquare_venues (
venueid VARCHAR(32) NOT NULL,
name VARCHAR(200),
url VARCHAR(4000),
address VARCHAR(200),
postalcode INT(5),
cc VARCHAR(4),
city VARCHAR(50),
state VARCHAR(50),
country VARCHAR(50),
latitude DOUBLE(10,8),
longitude DOUBLE(11,8),
PRIMARY KEY (venueid)
);

CREATE TABLE IF NOT EXISTS sms_messages (
smsid BIGINT(15) NOT NULL AUTO_INCREMENT,
userid INT(11) NOT NULL,
fingerprint VARCHAR(40) NOT NULL,
type VARCHAR(3),
conversation VARCHAR(500),
contact_num VARCHAR(20),
body VARCHAR(4000),
folder VARCHAR(6),
PRIMARY KEY (smsid),
UNIQUE KEY (userid, fingerprint)
);

CREATE TABLE IF NOT EXISTS sms_contacts (
userid INT(11) NOT NULL,
contact_num VARCHAR(20) NOT NULL,
contact_name VARCHAR(200) NOT NULL,
PRIMARY KEY (userid, contact_num)
);
