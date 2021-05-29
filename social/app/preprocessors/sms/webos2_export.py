import pandas as p
import datetime as d
import re
import hashlib
from pathlib import Path
import numpy as np


def open_file(filepath):
    df = p.read_csv(filepath, sep="\t")
    return df


def lambda_number_format(sender, recipients, regex):
    number = regex.sub("", str(sender) if sender != "self" else str(recipients))
    if len(number) == 10 and number[0] != "+":
        number = "+1" + number
    elif len(number) == 11 and number[0] == "1":
        number = "+" + number
    elif len(number) > 20:
        number = ""
    return number


def lambda_number_convo(sender, recipients, type, regex):
    number_convo = str(sender).split(", ") if sender != "self" else str(recipients).split(", ")
    if type == "type_aim":
        return "~".join(number_convo)
    elif len(number_convo) > 1:
        convo_out = list()
        for number in number_convo:
            convo_out.append(lambda_number_format("self", number, regex))
        return "~".join(convo_out)
    else:
        return ""


def lambda_fix_timestamp(timestamp, service_name):
    timestamp = int(timestamp)
    return timestamp if service_name == "sms" or len(str(timestamp)) < 11 else int(timestamp/1000)


def lambda_generate_id(list_of_attributes):
    for a in list_of_attributes:
        a = str(a)

    key = "_".join(list_of_attributes)

    key = key.encode("utf-8")

    return hashlib.sha1(key).hexdigest()


def column_transformations(df):
    # Fix timestamp for mms
    df["Timestamp"] = df.apply(lambda x: lambda_fix_timestamp(x["Timestamp"], x["ServiceName"]), axis=1)

    # Replace NaN in Message with ""
    df = df.replace(np.nan, "", regex=True)

    # Formatted number
    number_format = re.compile(r"[^\d+]+")
    df["contact_num"] = df.apply(lambda x: lambda_number_format(x["Sender"], x["Recipients"], number_format), axis=1)

    # For multiple recipients (rare), it'll go in the conversation column instead
    df["conversation"] = df.apply(lambda x: lambda_number_convo(x["Sender"], x["Recipients"],
                                                                x["ServiceName"], number_format), axis=1)

    # if AIM type was used, fix it (this does not cover other types, I don't have example data)
    df["ServiceName"] = df.apply(lambda x: "aim" if x["ServiceName"] == "type_aim" else x["ServiceName"], axis=1)

    # Date column and time column in the right format
    df["date"] = df.apply(lambda x: d.datetime.fromtimestamp(x["Timestamp"], tz=d.timezone.utc).date().strftime("%Y-%m-%d"), axis=1)
    df["time"] = df.apply(lambda x: d.datetime.fromtimestamp(x["Timestamp"], tz=d.timezone.utc).strftime("%H:%M:%S"), axis=1)

    # Generate the SHA1 ID of the row
    df["id"] = df.apply(lambda x: lambda_generate_id([x["date"], x["time"], x["contact_num"], x["Message"]]), axis=1)

    # Rename columns to match expected format
    df.rename(columns={
        "Message": "body",
        "Foldername": "folder",
        "ServiceName": "type"
    }, inplace=True)

    # Drop unneeded columns
    df = df.drop(labels=["Timestamp", "Recipients", "Sender", "DateTime"], axis=1)

    return df


def export(df, export_path):
    df.to_json(export_path, orient="records")
    return True


def batch_convert(directory_name):
    directory_path = Path(directory_name)
    for filepath in directory_path.iterdir():
        data = open_file(filepath)
        data = data[data.Timestamp != " "]
        data = column_transformations(data)
        filename = filepath.name
        listed_file = str(filename).split(".")[:-1]
        listed_file.append("json")
        output_fname = ".".join(listed_file)
        output_path = f"output/{output_fname}"
        export(data, output_path)


if __name__ == "__main__":
    directory = "input"
    batch_convert(directory)
