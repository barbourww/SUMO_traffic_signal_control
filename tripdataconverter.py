from xml.etree import ElementTree as ET


def parse_trip_info(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    trips = root.find('tripinfos')
    return [child.attrib for child in root]
