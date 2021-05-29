import datetime as dt
import re
import hashlib
import json
from pathlib import Path
import base64


def decode_mms_plaintext(base_64_str):
    message = base64.b64decode(base_64_str).decode("utf-16")

    return message


def attributes_to_json(process_text):
    # We can use double quotes as a somewhat reliable way to split the entry
    process_list = process_text.split("\"")

    kvp = {}

    for i in range(0, len(process_list) - 2):
        if process_list[i][-1] == "=":
            process_key_start = process_list[i].find(" ") + 1
            process_key = process_list[i][process_key_start:-1]
            i += 1
            kvp[process_key] = process_list[i]

    return kvp


def double_quote_shuffle(process_text, attribute=" body="):
    # body might be wrapped in single quotes if there are double quotes in the actual message, so flip that
    # Searching for " body=" is not completely foolproof if there is an attribute value with that inside it, but
    # in all likelihood the first instance of " body=" in the string will be the attribute. It will hit that before the
    # most dynamic piece of data in the string, which is the body value itself.
    body_pos = process_text.find(attribute) + len(attribute)

    if process_text[body_pos] == "'":
        body_end = process_text.find("'", body_pos + 1)
        body_text = process_text[body_pos+1:body_end]

        body_text = body_text.replace("\"", "&quot;")

        process_text = f"{process_text[:body_pos]}\"{body_text}\"{process_text[body_end+1:]}"

    return process_text


def number_formatting(contact_num, regex):
    contact_num = regex.sub("", contact_num)

    if len(contact_num) == 10 and contact_num[0] != "+":
        contact_num = "+1" + contact_num
    elif len(contact_num) == 11 and contact_num[0] == "1":
        contact_num = "+" + contact_num

    return contact_num


def process_single_sms(raw_text):
    # Process sms
    process_text = raw_text

    finalized_entry = {}

    address = get_field(process_text, "string") or get_field(process_text, "Sender")

    # Fixing contact number to match expected pattern
    number_format = re.compile(r"[^\d+]+")

    contact_num = number_formatting(address, number_format)

    finalized_entry["type"] = "sms"
    finalized_entry["contact_num"] = contact_num
    finalized_entry["body"] = get_field(process_text, "Body")

    return finalized_entry


def process_single_mms(raw_text):

    finalized_entry = {}

    index = 0
    address_list = []

    sender = None

    while raw_text.find("<string>", index) != -1:
        index = raw_text.find("<string>", index)
        address_list.append(get_field(raw_text, "string", index))
        index += 1

    sender = get_field(raw_text, "Sender")
    if sender not in address_list and sender:
        address_list.append(sender)

    regex = re.compile(r"[^\d+]+")

    conversation_list = []
    for addr in address_list:
        conversation_list.append(number_formatting(addr or "999999999", regex))
    conversation_list.sort()
    conversation = "~".join(conversation_list)

    finalized_entry["type"] = "mms"
    finalized_entry["conversation"] = conversation

    # Process parts
    index = 0
    list_of_items = []
    while raw_text.find("<MessageAttachment>", index) != -1:
        index = raw_text.find("<MessageAttachment>", index)
        message_attachment = get_field(raw_text, "MessageAttachment", index)
        index += 1

        if message_attachment:
            type = get_field(message_attachment, "AttachmentContentType")

            if "image" in type:
                list_of_items.append(type)
            elif type == "text/plain":
                list_of_items.append(decode_mms_plaintext(get_field(message_attachment, "AttachmentDataBase64String")))

    # print(list_of_items)

    # print(sender)

    finalized_entry["contact_num"] = sender or ""
    finalized_entry["body"] = "\n".join(list_of_items)

    return finalized_entry


def generate_id(list_of_attributes):
    for a in list_of_attributes:
        a = str(a)

    key = "_".join(list_of_attributes)

    key = key.encode("utf-8")

    return hashlib.sha1(key).hexdigest()


def get_field(msg, field_to_get, padding=0):
    start = msg.find(f"<{field_to_get}>", padding)
    if start != -1:
        start = start + len(field_to_get) + 2
        end = msg.find(f"</{field_to_get}", start)
        return msg[start:end]
    else:
        return False


def import_file_as_dict(filepath, chunksize):
    # Create empty list to populate with messages
    list_of_msgs = []
    try_reading = True

    # Open XML file for reading
    f = open(filepath, encoding="utf-8")

    # Get chunk of the file
    rawtext = f.read(chunksize)

    # Find starting point
    index = rawtext.find("<ArrayOfMessage") + 1

    while rawtext.find("<Message>", index) != -1:
        # Get start of single message
        start = rawtext.find("<Message>", index)
        if start >= 0:
            index = end = rawtext.find("</Message>", start) + 10
        else:
            index = start

        # Save off single message
        single_msg = rawtext[start:end]

        finalized_entry = {}

        # Get specialized SMS or MMS fields

        if "<Body>" in single_msg:
            finalized_entry = process_single_sms(single_msg)

        elif "<Attachments>" in single_msg or "<Recepients>" in single_msg:
            finalized_entry = process_single_mms(single_msg)

        # Get fields we anticipate to be in both

        timestamp = int(get_field(single_msg, "LocalTimestamp"))
        unix_time = int((timestamp - 116444736000000000) / 10000000)

        finalized_entry["date"] = dt.datetime.fromtimestamp(unix_time, tz=dt.timezone.utc).date().strftime("%Y-%m-%d")
        finalized_entry["time"] = dt.datetime.fromtimestamp(unix_time, tz=dt.timezone.utc).strftime("%H:%M:%S")

        finalized_entry["folder"] = "inbox" if get_field(single_msg, "IsIncoming") == "true" else "outbox"

        contact_for_id = finalized_entry.get("conversation") or finalized_entry.get("contact_num") or ""

        if contact_for_id or True:

            finalized_entry["id"] = generate_id([finalized_entry["date"], finalized_entry["time"],
                                                 contact_for_id, finalized_entry.get("body") or ""])

            list_of_msgs.append(finalized_entry)

        # if len(list_of_msgs) % 100 == 0:
        #     print(f"Processed {len(list_of_msgs)} messages")

        # If within 10,000,000 bytes of the end of what's in memory, dump everything that came before and grab
        # the next 500,000,000 bytes into memory

        if try_reading:
            if len(rawtext) - index < 10000000:
                to_add = f.read(chunksize)
                if len(to_add) > 0:
                    rawtext = rawtext[index:] + to_add
                    index = 0
                else:
                    try_reading = False

    # Close the XML file
    f.close()
    return list_of_msgs


def batch_convert(directory_name):
    directory_path = Path(directory_name)
    for filepath in directory_path.iterdir():
        file = import_file_as_dict(filepath, 250000000)
        filename = filepath.name
        listed_file = str(filename).split(".")[:-1]
        listed_file.append("json")
        output_fname = ".".join(listed_file)
        output_path = f"output/{output_fname}"
        output = open(output_path, "w")
        json.dump(file, output)


if __name__ == "__main__":
    batch_convert("input")
    # print(file)
