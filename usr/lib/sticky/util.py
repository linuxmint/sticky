#!/usr/bin/python3

import re
import xml.etree.ElementTree as etree

ip_number = r"(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])"
ip_address = r"(?:(?:" + ip_number + ".){3}" + ip_number + ")"
domain = r"(?:(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+)(?:\.(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+)*(?:\.(?:[a-z\u00a1-\uffff]{2,}))"

regex_string = r"(?:(?:https?|ftp)://)(?:\S+(?::\S*)?@)?(?:" + ip_address + r"|" + domain + r")(?::\d{2,5})?(?:/\S*)?(?:\?\S*)?$\Z"
regex = re.compile(regex_string, re.IGNORECASE)

def ends_with_url(string):
    return bool(regex.search(string))

def get_url_start(string):
    return regex.search(string)

# format conversion
GNOTE_TO_INTERNAL_MAP = {
    'bold': 'bold',
    'italic': 'italic',
    'underline': 'underline',
    'strikethrough': 'strikethrough',
    'highlight': 'highlight',
    'url': 'link',
}

GNOTE_NS_PREFIX = '{http://beatniksoftware.com/tomboy}'

def gnote_to_internal_format(file_path):
    tree = etree.parse(file_path)
    root = tree.getroot()

    info = {}
    info['title'] = root.find(GNOTE_NS_PREFIX + 'title').text

    def process_element(element):
        text = ''

        tag_name = element.tag.split('}')[1]
        if tag_name in GNOTE_TO_INTERNAL_MAP:
            internal_tag = '#tag:%s:' % GNOTE_TO_INTERNAL_MAP[tag_name]
            text += internal_tag
        else:
            internal_tag = ''

        if element.text:
            text += element.text

        for child in element:
            text += process_element(child)

        text += internal_tag

        if element.tail:
            text += element.tail

        return text

    info['text'] = process_element(root.find(GNOTE_NS_PREFIX + 'text').find(GNOTE_NS_PREFIX + 'note-content'))

    category = None
    try:
        tags = root.find(GNOTE_NS_PREFIX + 'tags')
        for tag in tags:
            if tag.text.startswith('system:notebook:'):
                category = tag.text[16:]
    except Exception as e:
        pass

    if category is None:
        category = _("Unfiled")

    return (category, info)
