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

junctions = traci.junction.getIDList()
traffic_lights = traci.trafficlight.getIDList()
traffic_lights_lanes = {}
traffic_lights_links = {}
print(len(traffic_lights), 'traffic lights in network\n')
assert(set(traffic_lights).issubset(set(junctions)))

for tl in traffic_lights:
    traci.junction.subscribeContext(objectID=tl, domain=tc.CMD_GET_VEHICLE_VARIABLE, dist=50,
                                    varIDs=[tc.VAR_SPEED, tc.VAR_WAITING_TIME, tc.VAR_ACCUMULATED_WAITING_TIME])
    traffic_lights_lanes[tl] = traci.trafficlight.getControlledLanes(tlsID=tl)
    traffic_lights_links[tl] = traci.trafficlight.getControlledLinks(tlsID=tl)

step = 0
arrived_veh_results = {}
old_veh_subscriptions = []

# run to completion
# while traci.simulation.getMinExpectedNumber() > 0:
# run to step number
while step < 150:
    print("\nStep", step)
    sim_time = traci.simulation.getCurrentTime()

    for dep_veh in traci.simulation.getDepartedIDList():
        traci.vehicle.subscribe(dep_veh, [tc.VAR_DISTANCE, tc.VAR_ACCUMULATED_WAITING_TIME])
    new_veh_subscriptions = traci.vehicle.getSubscriptionResults()

    cur_vehs = traci.vehicle.getIDList()
    print(len(cur_vehs), "active vehicles")
    arriving_vehs = traci.simulation.getArrivedIDList()
    print(len(arriving_vehs), "vehicles arriving", arriving_vehs)
    for av in arriving_vehs:
        arrived_veh_results[av] = old_veh_subscriptions[av]
        arrived_veh_results[av]['arr_time'] = step

    for tl in ["42435663"]:
        print(tl, '...')
        ryg_state = traci.trafficlight.getRedYellowGreenState(tlsID=tl)
        print(ryg_state)
        state_idx = traci.trafficlight.getPhase(tlsID=tl)
        state_remaining_time = (traci.trafficlight.getNextSwitch(tlsID=tl) - sim_time) / 1000
        print(state_remaining_time)
        tl_context = traci.junction.getContextSubscriptionResults(objectID=tl)
        print(tl_context)

        state_counts = {}

        if tl_context is not None:
            for veh in tl_context:
                try:
                    if traci.vehicle.getNextTLS(vehID=veh)[0][0] == tl:
                        # vehicle is on approach to this traffic light
                        veh_lane = traci.vehicle.getLaneID(vehID=veh)
                        lane_ryg_state = ryg_state[traffic_lights_lanes[tl].index(veh_lane)]
                        state_counts[lane_ryg_state.lower()] = state_counts.get(lane_ryg_state.lower(), 0) + 1
                        print(veh_lane in traffic_lights_lanes[tl], lane_ryg_state)
                except IndexError:
                    # vehicle is at the end of its route
                    pass

        if state_counts.get('r', 0) > state_counts.get('g', 0) and 'y' not in ryg_state:
            try:
                traci.trafficlight.setPhase(tlsID=tl, index=state_idx+1)
            except traci.exceptions.TraCIException:
                traci.trafficlight.setPhase(tlsID=tl, index=0)

    old_veh_subscriptions = copy(new_veh_subscriptions)
    traci.simulationStep()
    step += 1

print(arrived_veh_results)
traci.close(False)
