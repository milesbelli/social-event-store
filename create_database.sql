CREATE USER IF NOT EXISTS 'socialuser'@'localhost' IDENTIFIED BY 'resetme';

CREATE DATABASE IF NOT EXISTS social
CHARACTER SET utf8mb4
COLLATE utf8mb4_general_ci;

GRANT ALL PRIVILEGES ON social.* TO 'socialuser'@'localhost';

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