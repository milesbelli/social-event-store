import datetime as dt
import re
import hashlib
import json
from pathlib import Path


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
    contact_num = regex.sub("", contact_num) if "@" not in contact_num \
        else contact_num

    if len(contact_num) == 10 and contact_num[0] != "+":
        contact_num = "+1" + contact_num
    elif len(contact_num) == 11 and contact_num[0] == "1":
        contact_num = "+" + contact_num

    return contact_num


def decode_xml(text):
    text = text.replace("&quot;", "\"")
    text = text.replace("&apos;", "\'")

    while text.find("&#") != -1:
        start = text.find("&#")
        end = text.find(";", start)

        amp_text = text[start:end+1]
        if text[start+2] == "x":
            swap_dict = {"A": 10,
                         "D": 13}
            amp_num = swap_dict[text[start+3]]
        else:
            amp_num = int(text[start+2:end])

        text = text.replace(amp_text, chr(amp_num))


    text = text.replace("&amp;", "&")

    return text


def process_single_sms(raw_text):
    # Process sms
    process_text = raw_text

    # Change single quotes back to double quotes for body
    process_text = double_quote_shuffle(process_text, " body=")

    kvp = attributes_to_json(process_text)

    finalized_entry = {}

    # Fixing contact number to match expected pattern
    number_format = re.compile(r"[^\d+]+")

    contact_num = number_formatting(kvp["address"], number_format)

    # Change the milliseconds to seconds
    datesec = int(kvp["date"]) / 1000
    datesec = int(datesec)

    finalized_entry["type"] = "sms"
    finalized_entry["contact_num"] = contact_num
    finalized_entry["folder"] = "outbox" if kvp["type"] == "2" else "inbox"
    finalized_entry["body"] = decode_xml(kvp["body"])
    finalized_entry["date"] = dt.datetime.fromtimestamp(datesec, tz=dt.timezone.utc).date().strftime("%Y-%m-%d")
    finalized_entry["time"] = dt.datetime.fromtimestamp(datesec, tz=dt.timezone.utc).strftime("%H:%M:%S")
    finalized_entry["id"] = generate_id([finalized_entry["date"], finalized_entry["time"],
                                         finalized_entry["contact_num"], finalized_entry["body"]])
    finalized_entry["contact_name"] = kvp["contact_name"] if kvp["contact_name"] != "(Unknown)" else None

    return finalized_entry


def process_single_mms(raw_text):

    finalized_entry = {}

    # Process header
    start_header = raw_text.find("<mms ")
    end_header = raw_text.find(">", start_header) + 1
    header = raw_text[start_header:end_header]

    header_list = attributes_to_json(header)

    # print(header_list)

    datesec = int(int(header_list["date"]) / 1000)

    regex = re.compile(r"[^\d+~]+")
    address = header_list.get("address")
    address_list = address.split("~") if address else []
    conversation_list = []
    for addr in address_list:
        conversation_list.append(number_formatting(addr or "999999999", regex))
    conversation_list.sort()
    conversation = "~".join(conversation_list)

    finalized_entry["type"] = "mms"
    finalized_entry["conversation"] = conversation
    finalized_entry["folder"] = "outbox" if header_list["msg_box"] == "2" else "inbox"
    finalized_entry["date"] = dt.datetime.fromtimestamp(datesec, tz=dt.timezone.utc).date().strftime("%Y-%m-%d")
    finalized_entry["time"] = dt.datetime.fromtimestamp(datesec, tz=dt.timezone.utc).strftime("%H:%M:%S")

    # Process parts
    index = end_header
    list_of_items = []
    while index != -1:
        index = start = raw_text.find("<part seq=\"0\"", index + 1)
        end = raw_text.find(">", start + 1) + 1

        if index != -1:
            part_str = double_quote_shuffle(raw_text[start:end], " text=")
            part = attributes_to_json(part_str)

            if "image" in part["ct"]:
                list_of_items.append(part["ct"])
            elif part["ct"] == "text/plain":
                list_of_items.append(part["text"])

    # print(list_of_items)

    # Process recipients
    index = end_header
    sender = None
    while index != -1:
        index = start = raw_text.find("<addr ", index + 1)
        end = raw_text.find(">", start + 1) + 1

        if index != -1:
            addr = attributes_to_json(raw_text[start:end])

            if addr["type"] == "137":
                sender = number_formatting(addr["address"], regex)

    # print(sender)

    finalized_entry["contact_num"] = sender
    finalized_entry["body"] = decode_xml("\n".join(list_of_items))
    finalized_entry["id"] = generate_id([finalized_entry["date"], finalized_entry["time"],
                                         finalized_entry["conversation"], finalized_entry["body"]])

    return finalized_entry


def generate_id(list_of_attributes):
    for a in list_of_attributes:
        a = str(a)

    key = "_".join(list_of_attributes)

    key = key.encode("utf-8")

    return hashlib.sha1(key).hexdigest()


def import_file_as_dict(filepath, chunksize):
    # Create empty list to populate with messages
    list_of_msgs = []

    # Open XML file for reading
    f = open(filepath, encoding="utf-8")

    # Get chunk of the file
    rawtext = f.read(chunksize)

    # Find starting point
    index = rawtext.find("<smses") + 1

    eof_reached = False

    while index != -1:
        # Get start of single message
        start = rawtext.find("<", index)

        # End position is based on whether it's sms or mms, then process based on type
        if rawtext[start:start+4] == "<sms":
            index = end = rawtext.find("/>", start) + 2
            finalized_entry = process_single_sms(rawtext[start:end])
            list_of_msgs.append(finalized_entry)

        elif rawtext[start:start+4] == "<mms":
            index = end = rawtext.find("</mms>", start) + 6
            finalized_entry = process_single_mms(rawtext[start:end])
            list_of_msgs.append(finalized_entry)

        elif rawtext[start:start+7] == "</smses":
            break

        # If within 10,000,000 bytes of the end of what's in memory, dump everything that came before and grab
        # the next 500,000,000 bytes into memory

        if len(rawtext) - index < 10000000 and not eof_reached:
            to_add = f.read(chunksize)
            if len(to_add) > 0:
                rawtext = rawtext[index:] + to_add
                index = 0
            else:
                eof_reached = True

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
    # filepath = "input/sms-20210203184222.xml"
    filepath = "input/sample.xml"
    batch_convert("input")
    # print(file)
