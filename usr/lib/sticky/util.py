#!/usr/bin/python3

import re

ip_number = r"(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])"
ip_address = r"(?:(?:" + ip_number + ".){3}" + ip_number + ")"
domain = r"(?:(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+)(?:\.(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+)*(?:\.(?:[a-z\u00a1-\uffff]{2,}))"

regex_string = r"(?:(?:https?|ftp)://)(?:\S+(?::\S*)?@)?(?:" + ip_address + r"|" + domain + r")(?::\d{2,5})?(?:/\S*)?(?:\?\S*)?$\Z"
regex = re.compile(regex_string, re.IGNORECASE)

def ends_with_url(string):
    return bool(regex.search(string))

def get_url_start(string):
    return regex.search(string)
