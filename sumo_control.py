import os
import sys
from copy import copy
import re
import csv

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("SUMO_HOME not in system environment variables. Please declare variable.")

sumoBinaryCMD = "C:/Program Files (x86)/DLR/Sumo/bin/sumo.exe"
sumoBinaryGUI = "C:/Program Files (x86)/DLR/Sumo/bin/sumo-gui.exe"

sumoCmd = [sumoBinaryCMD, "-c", "./nyc.sumocfg"]


def write_vehicle_results(all_arrived_vehicles, last_wrote_results_step, filename):
    with open(filename, 'a') as f:
        w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
        for veh in all_arrived_vehicles:
            if veh['arr_time'] > last_wrote_results_step:
                w.writerow([veh[watching_vehicle_vars[k]] for k in watching_vehicle_vars_keys + ['arr_time']])


def write_intersecction_results(all_intersections, last_wrote_results_step, filename):
    with open(filename, 'a') as f:
        w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)

import traci
import traci.constants as tc

# INPUTS
signal_switch_time_overcome = 5
signal_switch_vehicles_overcome = 4
approaching_vehicle_vars = {'speed': tc.VAR_SPEED, 'waiting_time': tc.VAR_WAITING_TIME,
                            'accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}
watching_vehicle_vars = {'distance': tc.VAR_DISTANCE, 'total_accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}
write_results_interval = 100
# ------

approaching_vehicle_vars_keys = approaching_vehicle_vars.keys()
watching_vehicle_vars_keys = watching_vehicle_vars.keys()

results_path = './results/'
next_trial_num = max([int(tn.group(1)) for tn in
                      [re.search('[A-z]*([0-9]*).csv', fn) for fn in os.listdir('./results')]]) + 1
trial_filename_vehs = os.path.join(results_path, 'adaptive{}_vehs.csv'.format(next_trial_num))
trial_filename_junc = os.path.join(results_path, 'adaptive{}_junc.csv'.format(next_trial_num))

# ----------------
# BEGIN SIMULATION
# ----------------
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
                                    varIDs=approaching_vehicle_vars.values())
    traffic_lights_lanes[tl] = traci.trafficlight.getControlledLanes(tlsID=tl)
    traffic_lights_links[tl] = traci.trafficlight.getControlledLinks(tlsID=tl)

step = 0
last_wrote_results = -1
arrived_veh_results = {}
old_veh_subscriptions = []

# run to completion
# while traci.simulation.getMinExpectedNumber() > 0:
# run to step number
while step < 150:
    print("\nStep", step)
    sim_time = traci.simulation.getCurrentTime()

    for dep_veh in traci.simulation.getDepartedIDList():
        traci.vehicle.subscribe(dep_veh, watching_vehicle_vars.values())
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
        if 'y' not in ryg_state:
            if state_counts.get('r', 0) >= state_counts.get('g', 0) + signal_switch_vehicles_overcome:
                if state_remaining_time <= signal_switch_time_overcome:
                    try:
                        traci.trafficlight.setPhase(tlsID=tl, index=state_idx+1)
                    except traci.exceptions.TraCIException:
                        traci.trafficlight.setPhase(tlsID=tl, index=0)

    old_veh_subscriptions = copy(new_veh_subscriptions)
    if step % write_results_interval == 0:
        write_vehicle_results(all_arrived_vehicles=arrived_veh_results, last_wrote_results_step=last_wrote_results,
                              filename=trial_filename_vehs)
        last_wrote_results = step

    traci.simulationStep()
    step += 1

print(arrived_veh_results)
traci.close(False)

