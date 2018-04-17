import xml.etree.ElementTree as ET
from random import randint
import os


def randomize_timings(program_time):
    if 'nyc_tl_random{}.net.xml'.format(program_time) in os.listdir("./net_files"):
        return 'net_files/nyc_tl_random{}.net.xml'.format(program_time)

    print("Making random program for program_time={}".format(program_time))

    tree = ET.parse('nyc_edit.net.xml')
    print(type(tree))
    root = tree.getroot()

    tags = set([child.tag for child in root])
    print("All tags:", tags)

    for child in root.findall('tlLogic'):
        child.attrib['offset'] = str(randint(0, 60))

    tree.write('net_files/nyc_tl_random{}.net.xml'.format(program_time), encoding='utf-8', xml_declaration=True)
    return 'net_files/nyc_tl_random{}.net.xml'.format(program_time)
