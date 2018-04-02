import xml.etree.ElementTree as ET
import networkx as nx
from itertools import combinations

tree = ET.parse('nyc_edit.net.xml')
root = tree.getroot()

tags = set([child.tag for child in root])
print("All tags:", tags)
for t in tags:
    attr = set([])
    for child in root.findall(t):
        attr.update(set(child.attrib.keys()))
    print(t, ':', attr)
    for a in attr:
        vals = set([])
        for child in root.findall(t):
            vals.update([child.get(a)])
        print('\t', a, ':', vals)
print('\n\n')

deadends = [(j.get('id'), len(j.get('incLanes').split(' '))) for j in root.findall('junction')
            if j.get('type') == 'dead_end']
print(len(deadends), "dead ends on network")
print(deadends, '\n\n')

g = nx.DiGraph()
g.add_nodes_from([j.get('id') for j in root.findall('junction') if j.get('id') is not None])
pos = {j.get('id'): (float(j.get('x')), float(j.get('y'))) for j in root.findall('junction') if j.get('id') is not None}
g.add_edges_from([(e.get('from'), e.get('to'),
                   {'length': ((pos[e.get('from')][0] - pos[e.get('to')][0])**2 + (pos[e.get('from')][1] - pos[e.get('to')][1])**2)**0.5,
                    'id': e.get('id')})
                  for e in root.findall('edge') if e.get('from') is not None and e.get('to') is not None])
# nx.draw(g, pos={j.get('id'): (j.get('x'), j.get('y')) for j in root.findall('junction')
#                 if j.get('id') is not None})
# plt.show()
print(nx.shortest_path(g, '4207932666', '42447230'))

routes = ET.Element('routes')
rtree = ET.ElementTree(element=routes)
v1 = ET.SubElement(routes, 'vType', attrib={'id': 'type1', 'length': '5', 'maxSpeed': '11.0'})
paths = []
n_comb = len(list(combinations(deadends, r=2)))
for (d1, l1), (d2, l2) in combinations(deadends, r=2):
    try:
        l = nx.shortest_path_length(g, source=d1, target=d2, weight='length')
        e = nx.shortest_path(g, source=d1, target=d2, weight='length')
        paths.append((d1, d2, g[d1][e[1]]['id'], g[e[-2]][d2]['id'], l1, l2, l))
    except (nx.exception.NetworkXNoPath, IndexError):
        pass
print("Found {} of {} paths with routes.".format(len(paths), n_comb))
paths.sort(key=lambda x: x[-1], reverse=True)
add_paths_prop = 1.0
for orig, dest, first_edge, last_edge, lanes1, lanes2, leng in paths[:int(len(paths)*add_paths_prop)]:
    f = ET.SubElement(routes, 'flow',
                      attrib={'id': '{}-{}'.format(orig, dest), 'begin': '0', 'end': '7200',
                              'vehsPerHour': str(lanes1*360.),
                              'from': first_edge, 'to': last_edge, 'type': 'type1'})
print("Added {} flows.".format(int(len(paths)*add_paths_prop)))
rtree.write('nyc_routes.rou.xml', encoding='utf-8', xml_declaration=True)
