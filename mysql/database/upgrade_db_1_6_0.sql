USE social;

ALTER TABLE sms_messages
MODIFY COLUMN contact_num VARCHAR(300);