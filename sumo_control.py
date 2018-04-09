import os
import sys
from copy import copy

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("SUMO_HOME not in system environment variables. Please declare variable.")

sumoBinaryCMD = "C:/Program Files (x86)/DLR/Sumo/bin/sumo.exe"
sumoBinaryGUI = "C:/Program Files (x86)/DLR/Sumo/bin/sumo-gui.exe"

sumoCmd = [sumoBinaryCMD, "-c", "./nyc.sumocfg"]

import traci
import traci.constants as tc
traci.start(sumoCmd)
print("Simulation loaded.")

junc = "42435645"
junctions = traci.junction.getIDList()
traffic_lights = traci.trafficlight.getIDList()
traffic_lights_lanes = {}
print(len(traffic_lights), 'traffic lights in network\n')
assert(set(traffic_lights).issubset(set(junctions)))

for tl in traffic_lights:
    traci.junction.subscribeContext(objectID=tl, domain=tc.CMD_GET_VEHICLE_VARIABLE, dist=50,
                                    varIDs=[tc.VAR_SPEED, tc.VAR_WAITING_TIME, tc.VAR_ACCUMULATED_WAITING_TIME])
    traffic_lights_lanes[tl] = traci.trafficlight.getControlledLanes(tlsID=tl)

step = 0
arrived_veh_results = {}
old_veh_subscriptions = []

# run to completion
# while traci.simulation.getMinExpectedNumber() > 0:
# run to step number
while step < 150:
    print("Step", step)

    for dep_veh in traci.simulation.getDepartedIDList():
        traci.vehicle.subscribe(dep_veh, [tc.VAR_DISTANCE, tc.VAR_ACCUMULATED_WAITING_TIME])
    new_veh_subscriptions = traci.vehicle.getSubscriptionResults()

    tl_context = traci.junction.getContextSubscriptionResults(objectID=junc)
    print(tl_context)
    cur_vehs = traci.vehicle.getIDList()
    print(len(cur_vehs), "active vehicles")

    arriving_vehs = traci.simulation.getArrivedIDList()
    print(len(arriving_vehs), "vehicles arriving", arriving_vehs)
    for av in arriving_vehs:
        arrived_veh_results[av] = old_veh_subscriptions[av]
        arrived_veh_results[av]['arr_time'] = step

    if tl_context is not None:
        for veh in tl_context:
            try:
                if traci.vehicle.getNextTLS(vehID=veh)[0][0] == junc:
                    # vehicle is on approach to this traffic light
                    veh_lane = traci.vehicle.getLaneID(vehID=veh)
                    print(veh_lane in traffic_lights_lanes[junc])
            except IndexError:
                # vehicle is at the end of its route
                pass

    old_veh_subscriptions = copy(new_veh_subscriptions)
    traci.simulationStep()
    step += 1

print(arrived_veh_results)
traci.close(False)
