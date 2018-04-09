import xml.etree.ElementTree as ET
from random import randint

tree = ET.parse('nyc_edit.net.xml')
print(type(tree))
root = tree.getroot()

tags = set([child.tag for child in root])
print("All tags:", tags)

for child in root.findall('tlLogic'):
    child.attrib['offset'] = str(randint(0, 60))

tree.write('nyc_tl_random.net.xml', encoding='utf-8', xml_declaration=True)
