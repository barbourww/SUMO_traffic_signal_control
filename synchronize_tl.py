import xml.etree.ElementTree as ET
import time

tree = ET.parse('nyc_edit.net.xml')
print(type(tree))
root = tree.getroot()

tags = set([child.tag for child in root])
print("All tags:", tags)

#calculate vector for each edge and sort edges into minor (NW to SE) or major (NE to SW)
major = []
for edge in root.findall('edge'):
	if not('function' in edge.attrib):
		toID = edge.attrib['to']
		fromID = edge.attrib['from']
		for junction in root.findall('junction'):
			if junction.attrib['id'] == toID:
				toxcoord = float(junction.attrib['x'])
				toycoord = float(junction.attrib['y'])
			elif junction.attrib['id'] == fromID:
				fromxcoord = float(junction.attrib['x'])
				fromycoord = float(junction.attrib['y'])
		vectx = toxcoord - fromxcoord 
		vecty = toycoord - fromycoord
		if (vectx > 0 and vecty > 0) or (vectx < 0 and vecty < 0): #NE to SW
			major.append(edge.attrib['id'])
		
#want to start traffic light phases such that connections between major edges are green first
for tl in root.findall('tlLogic'):
	tlID = tl.attrib['id']
	for connection in root.findall('connection'):
		if 'tl' in connection.attrib and connection.attrib['tl'] == tlID and connection.attrib['to'] in major and connection.attrib['from'] in major:
			linkIndex = int(connection.attrib['linkIndex'])
			break
		linkIndex = -1
	if linkIndex > -1:
		phases = []
		for phase in tl.findall('phase'):
			phases.append([phase.attrib['duration'], phase.attrib['state']])
		while phases[0][1][linkIndex] != 'G' and phases[0][1][linkIndex] != 'g':
			firstphase = phases[0]
			for i in range(0,len(phases)-1):
				phases[i] = phases[i+1]
			phases[len(phases)-1] = firstphase
		j = 0
		for phase in tl.findall('phase'):
			phase.attrib['duration'] = phases[j][0]
			phase.attrib['state'] = phases[j][1]
			j = j + 1

#for each traffic light
#	get id
#	for each connection
#		if tl id exists and matches and to id is major and from id is major
#			get link index
#	look at phases for traffic light 
#		while value in index id in first phase is not 'G' or 'g', move phase to bottom
#		this should keep the phase pattern intact to prevent conflicts
			
	desiredduration = 90
	totalduration = 0
	durations = []
	for phase in tl.findall('phase'):
		durations.append(int(phase.attrib['duration']))
	totalduration = sum(durations)
	if totalduration != desiredduration:
		for d in range(0,len(durations)):
			durations[d] = round(durations[d] / totalduration * desiredduration)
		if sum(durations) != desiredduration:
			durations[len(durations)-1] = durations[len(durations)-1] + desiredduration - sum(durations)
		k = 0
		for phase in tl.findall('phase'):
			phase.attrib['duration'] = str(durations[k])
			k = k + 1
	totalduration = 0
	for phase in tl.findall('phase'):
		totalduration = totalduration + int(phase.attrib['duration'])	
	if totalduration != desiredduration:	
		print(totalduration)
		print(tlID)
#	store all phase durations as ints in list (for easier arithmetic)
#	if total duration is not equal to desired total duration
#		change duration to current/total*desired (same fraction of new total)
#		check for rounding error
#			add error to last duration
#		modify phase durations accoding to duration list
#	check total duration of phases and print errors

tree.write('nyc_tl_synchronized.net.xml', encoding='utf-8', xml_declaration=True)