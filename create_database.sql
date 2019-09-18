CREATE USER IF NOT EXISTS 'lmitas'@'localhost' IDENTIFIED BY 'resetme';

CREATE DATABASE IF NOT EXISTS social;

GRANT ALL PRIVILEGES ON social.* TO 'lmitas'@'localhost';

USE social;

CREATE TABLE IF NOT EXISTS events (
eventid INT(11) NOT NULL AUTO_INCREMENT,
userid INT(11) NOT NULL,
eventdate DATE NOT NULL,
eventtime TIME,
tweetid BIGINT(20),
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