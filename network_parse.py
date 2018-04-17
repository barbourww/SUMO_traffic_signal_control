import xml.etree.ElementTree as ET
import networkx as nx
from itertools import combinations
import os


def write_route_flows(veh_scale):
    if 'nyc_routes_scale{}.rou.xml'.format(veh_scale) in os.listdir("./route_files"):
        return 'route_files/nyc_routes_scale{}.rou.xml'.format(veh_scale)

    print("Making route file for veh_scale={}".format(veh_scale))

    tree = ET.parse('nyc_edit.net.xml')
    root = tree.getroot()

    tags = set([child.tag for child in root])
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

    deadends = [(j.get('id'), len(j.get('incLanes').split(' '))) for j in root.findall('junction')
                if j.get('type') == 'dead_end']

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

    routes = ET.Element('routes')
    rtree = ET.ElementTree(element=routes)
    v1 = ET.SubElement(routes, 'vType', attrib={'id': 'type1', 'length': '5', 'maxSpeed': '11.0', 'color': 'yellow'})
    v2 = ET.SubElement(routes, 'vType', attrib={'id': 'type2', 'length': '10', 'maxSpeed': '9.0', 'color': 'blue'})
    paths = []
    n_comb = len(list(combinations(deadends, r=2)))
    for (d1, l1), (d2, l2) in combinations(deadends, r=2):
        try:
            l = nx.shortest_path_length(g, source=d1, target=d2, weight='length')
            e = nx.shortest_path(g, source=d1, target=d2, weight='length')
            paths.append((d1, d2, g[d1][e[1]]['id'], g[e[-2]][d2]['id'], l1, l2, l))
        except (nx.exception.NetworkXNoPath, IndexError):
            pass
    paths.sort(key=lambda x: x[-1], reverse=True)
    add_paths_prop = 1.0
    for orig, dest, first_edge, last_edge, lanes1, lanes2, leng in paths[:int(len(paths)*add_paths_prop)]:
        f1 = ET.SubElement(routes, 'flow',
                           attrib={'id': '{}-{}_vt1'.format(orig, dest), 'begin': '0', 'end': '3600',
                                   'vehsPerHour': str(lanes1 * 10 * veh_scale),
                                   'from': first_edge, 'to': last_edge, 'type': 'type1'})
        f2 = ET.SubElement(routes, 'flow',
                           attrib={'id': '{}-{}_vt2'.format(orig, dest), 'begin': '0', 'end': '3600',
                                   'vehsPerHour': str(lanes1 * 1 * veh_scale),
                                   'from': first_edge, 'to': last_edge, 'type': 'type2'})
    rtree.write('route_files/nyc_routes_scale{}.rou.xml'.format(veh_scale), encoding='utf-8', xml_declaration=True)
    return 'route_files/nyc_routes_scale{}.rou.xml'.format(veh_scale)
