import multiprocessing as mp
import signal
import traceback
import os
import csv
import datetime as dt
import time
import sys
import re
from copy import copy
from itertools import product

from synchronize_tl import route_sync_traffic_lights
from network_parse import write_route_flows
from randomize_tl_offset import randomize_timings

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("SUMO_HOME not in system environment variables. Please declare variable.")

sumoBinaryCMD = "C:/Program Files (x86)/DLR/Sumo/bin/sumo.exe"
sumoBinaryGUI = "C:/Program Files (x86)/DLR/Sumo/bin/sumo-gui.exe"

generic_config = "./nyc_generic.sumocfg"

import traci
import traci.constants as tc


def get_sumo_cmd(veh_scale, program_time, random_or_sync, trip_info_filename):
    if random_or_sync == 'random':
        net_file = randomize_timings(program_time=program_time)
    elif random_or_sync == 'sync':
        net_file = route_sync_traffic_lights(program_time=program_time)
    else:
        raise ValueError
    route_file = write_route_flows(veh_scale=veh_scale)

    return [sumoBinaryCMD, "-c", "./nyc_generic.sumocfg", "-r", route_file, "-n", net_file, "--tripinfo-output", trip_info_filename]


def write_vehicle_results(all_arrived_vehicles, last_wrote_results_step, filename, header, header_var_dict):
    with open(filename, 'a') as f:
        w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
        for veh, veh_vals in all_arrived_vehicles.items():
            if veh_vals['arr_time'] > last_wrote_results_step:
                w.writerow([veh_vals[header_var_dict.get(k, k)] for k in header])


def write_epoch_results(all_epochs, last_wrote_results_step, filename, header):
    with open(filename, 'a') as f:
        w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
        for epoch_result in all_epochs:
            if epoch_result['epoch'] > last_wrote_results_step:
                w.writerow([epoch_result.get(k, '') for k in header])


def random_signal_timing(veh_flow_scale, tl_program_time, trial_num, write_results_interval=800):
    try:
        print("Simulation on process {}".format(mp.current_process().name))

        # Establish variables to monitor throughout simulation and write to CSV
        # ---------------------------------------------------------------------
        approaching_vehicle_vars = {'speed': tc.VAR_SPEED, 'waiting_time': tc.VAR_WAITING_TIME,
                                    'accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}
        watching_vehicle_vars = {'distance': tc.VAR_DISTANCE,
                                 'total_accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}

        watching_vehicle_vars_keys = list(watching_vehicle_vars.keys())
        vehicle_csv_header = ['veh_ID'] + watching_vehicle_vars_keys + ['dep_time', 'arr_time', 'teleported']
        simulation_csv_header = ['epoch', 'cumulative_distance', 'cumulative_waiting_time']

        results_path = './other_results/'
        trial_filename_vehs = os.path.join(results_path, 'random{}_vehs.csv'.format(trial_num))
        trial_filename_sim = os.path.join(results_path, 'random{}_sim.csv'.format(trial_num))
        trial_filename_trip_info = os.path.join(results_path, 'random{}_trip_info.xml'.format(trial_num))

        sumoCmd = get_sumo_cmd(veh_scale=veh_flow_scale, program_time=tl_program_time, random_or_sync='random',
                               trip_info_filename=trial_filename_trip_info)

        with open(trial_filename_vehs, 'a') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
            w.writerow(vehicle_csv_header)
        with open(trial_filename_sim, 'a') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
            w.writerow(simulation_csv_header)
        # ---------------------------------------------------------------------

        # ----------------
        # BEGIN SIMULATION
        # ----------------
        traci.start(sumoCmd)
        print("Simulation loaded.", trial_num)

        junctions = traci.junction.getIDList()
        traffic_lights = traci.trafficlight.getIDList()
        traffic_lights_lanes = {}
        traffic_lights_links = {}
        print(len(traffic_lights), 'traffic lights in network\n')
        assert (set(traffic_lights).issubset(set(junctions)))

        for tl in traffic_lights:
            traci.junction.subscribeContext(objectID=tl, domain=tc.CMD_GET_VEHICLE_VARIABLE, dist=50,
                                            varIDs=approaching_vehicle_vars.values())
            traffic_lights_lanes[tl] = traci.trafficlight.getControlledLanes(tlsID=tl)
            traffic_lights_links[tl] = traci.trafficlight.getControlledLinks(tlsID=tl)

        step = 0
        # will write on first factor of write_results_interval
        last_wrote_results = 0
        arrived_veh_results = {}
        vehicle_departure_times = {}
        old_veh_subscriptions = []
        epoch_results = []
        teleport_vehicles = set([])

        # run to step number
        # while step < 1000:
        # run to completion
        while traci.simulation.getMinExpectedNumber() > 0:
            # print("Step", step)

            new_teleports = traci.simulation.getStartingTeleportIDList()
            teleport_vehicles.update(set(new_teleports))

            for dep_veh in traci.simulation.getDepartedIDList():
                traci.vehicle.subscribe(dep_veh, watching_vehicle_vars.values())
                vehicle_departure_times[dep_veh] = step
            new_veh_subscriptions = traci.vehicle.getSubscriptionResults()

            cur_vehs = traci.vehicle.getIDList()

            this_epoch_result = {}
            this_epoch_dist = 0
            this_epoch_cumul_wait = 0
            for cv in cur_vehs:
                this_epoch_dist += new_veh_subscriptions[cv][tc.VAR_DISTANCE]
                this_epoch_cumul_wait += new_veh_subscriptions[cv][tc.VAR_ACCUMULATED_WAITING_TIME]
            this_epoch_result['cumulative_distance'] = this_epoch_dist
            this_epoch_result['cumulative_waiting_time'] = this_epoch_cumul_wait
            this_epoch_result['epoch'] = step
            epoch_results.append(this_epoch_result)

            # handle arriving vehicles for results recording
            arriving_vehs = traci.simulation.getArrivedIDList()
            for av in arriving_vehs:
                arrived_veh_results[av] = old_veh_subscriptions[av]
                arrived_veh_results[av]['arr_time'] = step
                arrived_veh_results[av]['dep_time'] = vehicle_departure_times[av]
                arrived_veh_results[av]['teleported'] = av in teleport_vehicles
                arrived_veh_results[av]['veh_ID'] = av

            old_veh_subscriptions = copy(new_veh_subscriptions)
            if step % write_results_interval == 0:
                write_vehicle_results(all_arrived_vehicles=arrived_veh_results,
                                      last_wrote_results_step=last_wrote_results,
                                      filename=trial_filename_vehs, header=vehicle_csv_header,
                                      header_var_dict=watching_vehicle_vars)
                write_epoch_results(all_epochs=epoch_results, last_wrote_results_step=last_wrote_results,
                                    filename=trial_filename_sim, header=simulation_csv_header)
                last_wrote_results = step

            traci.simulationStep()
            step += 1

        write_vehicle_results(all_arrived_vehicles=arrived_veh_results,
                              last_wrote_results_step=last_wrote_results,
                              filename=trial_filename_vehs, header=vehicle_csv_header,
                              header_var_dict=watching_vehicle_vars)
        write_epoch_results(all_epochs=epoch_results, last_wrote_results_step=last_wrote_results,
                            filename=trial_filename_sim, header=simulation_csv_header)
        traci.close(False)
        print("Simulation finished", trial_num)

    except BaseException as e:
        print("EXCEPTION ON PROCESS {}".format(mp.current_process().name))
        traceback.print_exc()
        return 'EXCEPTION'


def synchronized_signal_timing(veh_flow_scale, tl_program_time, trial_num, write_results_interval=800):
    try:
        print("Simulation on process {}".format(mp.current_process().name))

        # Establish variables to monitor throughout simulation and write to CSV
        # ---------------------------------------------------------------------
        approaching_vehicle_vars = {'speed': tc.VAR_SPEED, 'waiting_time': tc.VAR_WAITING_TIME,
                                    'accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}
        watching_vehicle_vars = {'distance': tc.VAR_DISTANCE,
                                 'total_accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}

        watching_vehicle_vars_keys = list(watching_vehicle_vars.keys())
        vehicle_csv_header = ['veh_ID'] + watching_vehicle_vars_keys + ['dep_time', 'arr_time', 'teleported']
        simulation_csv_header = ['epoch', 'cumulative_distance', 'cumulative_waiting_time']

        results_path = './other_results/'
        trial_filename_vehs = os.path.join(results_path, 'sync{}_vehs.csv'.format(trial_num))
        trial_filename_sim = os.path.join(results_path, 'sync{}_sim.csv'.format(trial_num))
        trial_filename_trip_info = os.path.join(results_path, 'sync{}_trip_info.xml'.format(trial_num))

        sumoCmd = get_sumo_cmd(veh_scale=veh_flow_scale, program_time=tl_program_time, random_or_sync='sync',
                               trip_info_filename=trial_filename_trip_info)

        with open(trial_filename_vehs, 'a') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
            w.writerow(vehicle_csv_header)
        with open(trial_filename_sim, 'a') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
            w.writerow(simulation_csv_header)
        # ---------------------------------------------------------------------

        # ----------------
        # BEGIN SIMULATION
        # ----------------
        traci.start(sumoCmd)
        print("Simulation loaded.", trial_num)

        junctions = traci.junction.getIDList()
        traffic_lights = traci.trafficlight.getIDList()
        traffic_lights_lanes = {}
        traffic_lights_links = {}
        print(len(traffic_lights), 'traffic lights in network\n')
        assert (set(traffic_lights).issubset(set(junctions)))

        for tl in traffic_lights:
            traci.junction.subscribeContext(objectID=tl, domain=tc.CMD_GET_VEHICLE_VARIABLE, dist=50,
                                            varIDs=approaching_vehicle_vars.values())
            traffic_lights_lanes[tl] = traci.trafficlight.getControlledLanes(tlsID=tl)
            traffic_lights_links[tl] = traci.trafficlight.getControlledLinks(tlsID=tl)

        step = 0
        # will write on first factor of write_results_interval
        last_wrote_results = 0
        arrived_veh_results = {}
        vehicle_departure_times = {}
        old_veh_subscriptions = []
        epoch_results = []
        teleport_vehicles = set([])

        # run to step number
        # while step < 1000:
        # run to completion
        while traci.simulation.getMinExpectedNumber() > 0:
            # print("Step", step)

            new_teleports = traci.simulation.getStartingTeleportIDList()
            teleport_vehicles.update(set(new_teleports))

            for dep_veh in traci.simulation.getDepartedIDList():
                traci.vehicle.subscribe(dep_veh, watching_vehicle_vars.values())
                vehicle_departure_times[dep_veh] = step
            new_veh_subscriptions = traci.vehicle.getSubscriptionResults()

            cur_vehs = traci.vehicle.getIDList()

            this_epoch_result = {}
            this_epoch_dist = 0
            this_epoch_cumul_wait = 0
            for cv in cur_vehs:
                this_epoch_dist += new_veh_subscriptions[cv][tc.VAR_DISTANCE]
                this_epoch_cumul_wait += new_veh_subscriptions[cv][tc.VAR_ACCUMULATED_WAITING_TIME]
            this_epoch_result['cumulative_distance'] = this_epoch_dist
            this_epoch_result['cumulative_waiting_time'] = this_epoch_cumul_wait
            this_epoch_result['epoch'] = step
            epoch_results.append(this_epoch_result)

            # handle arriving vehicles for results recording
            arriving_vehs = traci.simulation.getArrivedIDList()
            for av in arriving_vehs:
                arrived_veh_results[av] = old_veh_subscriptions[av]
                arrived_veh_results[av]['arr_time'] = step
                arrived_veh_results[av]['dep_time'] = vehicle_departure_times[av]
                arrived_veh_results[av]['teleported'] = av in teleport_vehicles
                arrived_veh_results[av]['veh_ID'] = av

            old_veh_subscriptions = copy(new_veh_subscriptions)
            if step % write_results_interval == 0:
                write_vehicle_results(all_arrived_vehicles=arrived_veh_results,
                                      last_wrote_results_step=last_wrote_results,
                                      filename=trial_filename_vehs, header=vehicle_csv_header,
                                      header_var_dict=watching_vehicle_vars)
                write_epoch_results(all_epochs=epoch_results, last_wrote_results_step=last_wrote_results,
                                    filename=trial_filename_sim, header=simulation_csv_header)
                last_wrote_results = step

            traci.simulationStep()
            step += 1

        write_vehicle_results(all_arrived_vehicles=arrived_veh_results,
                              last_wrote_results_step=last_wrote_results,
                              filename=trial_filename_vehs, header=vehicle_csv_header,
                              header_var_dict=watching_vehicle_vars)
        write_epoch_results(all_epochs=epoch_results, last_wrote_results_step=last_wrote_results,
                            filename=trial_filename_sim, header=simulation_csv_header)
        traci.close(False)
        print("Simulation finished", trial_num)

    except BaseException as e:
        print("EXCEPTION ON PROCESS {}".format(mp.current_process().name))
        traceback.print_exc()
        return 'EXCEPTION'


def adaptive_traffic_lights(signal_switch_time_overcome, signal_switch_vehicles_overcome, signal_sync_interval,
                            veh_flow_scale, tl_program_time,
                            trial_num, write_results_interval=800):
    try:
        print("Simulation on process {}".format(mp.current_process().name))

        # Establish variables to monitor throughout simulation and write to CSV
        # ---------------------------------------------------------------------
        approaching_vehicle_vars = {'speed': tc.VAR_SPEED, 'waiting_time': tc.VAR_WAITING_TIME,
                                    'accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}
        watching_vehicle_vars = {'distance': tc.VAR_DISTANCE,
                                 'total_accumulated_waiting_time': tc.VAR_ACCUMULATED_WAITING_TIME}

        watching_vehicle_vars_keys = list(watching_vehicle_vars.keys())
        vehicle_csv_header = ['veh_ID'] + watching_vehicle_vars_keys + ['dep_time', 'arr_time', 'teleported']
        simulation_csv_header = ['epoch', 'cumulative_distance', 'cumulative_waiting_time']

        results_path = './other_results/'
        trial_filename_vehs = os.path.join(results_path, 'adaptive{}_vehs.csv'.format(trial_num))
        trial_filename_sim = os.path.join(results_path, 'adaptive{}_sim.csv'.format(trial_num))
        trial_filename_trip_info = os.path.join(results_path, 'adaptive{}_trip_info.xml'.format(trial_num))

        sumoCmd = get_sumo_cmd(veh_scale=veh_flow_scale, program_time=tl_program_time, random_or_sync='sync',
                               trip_info_filename=trial_filename_trip_info)

        with open(trial_filename_vehs, 'a') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
            w.writerow(vehicle_csv_header)
        with open(trial_filename_sim, 'a') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_NONE)
            w.writerow(simulation_csv_header)
        # ---------------------------------------------------------------------

        # ----------------
        # BEGIN SIMULATION
        # ----------------
        traci.start(sumoCmd)
        print("Simulation loaded.", trial_num)

        junctions = traci.junction.getIDList()
        traffic_lights = traci.trafficlight.getIDList()
        traffic_lights_lanes = {}
        traffic_lights_links = {}
        assert (set(traffic_lights).issubset(set(junctions)))

        for tl in traffic_lights:
            traci.junction.subscribeContext(objectID=tl, domain=tc.CMD_GET_VEHICLE_VARIABLE, dist=50,
                                            varIDs=approaching_vehicle_vars.values())
            traffic_lights_lanes[tl] = traci.trafficlight.getControlledLanes(tlsID=tl)
            traffic_lights_links[tl] = traci.trafficlight.getControlledLinks(tlsID=tl)

        step = 0
        # will write on first factor of write_results_interval
        last_wrote_results = 0
        arrived_veh_results = {}
        vehicle_departure_times = {}
        old_veh_subscriptions = []
        epoch_results = []
        teleport_vehicles = set([])

        # run to step number
        # while step < 1000:
        # run to completion
        while traci.simulation.getMinExpectedNumber() > 0:
            # print("Step", step)
            sim_time = traci.simulation.getCurrentTime()

            new_teleports = traci.simulation.getStartingTeleportIDList()
            teleport_vehicles.update(set(new_teleports))

            for dep_veh in traci.simulation.getDepartedIDList():
                traci.vehicle.subscribe(dep_veh, watching_vehicle_vars.values())
                vehicle_departure_times[dep_veh] = step
            new_veh_subscriptions = traci.vehicle.getSubscriptionResults()

            cur_vehs = traci.vehicle.getIDList()

            this_epoch_result = {}
            this_epoch_dist = 0
            this_epoch_cumul_wait = 0
            for cv in cur_vehs:
                this_epoch_dist += new_veh_subscriptions[cv][tc.VAR_DISTANCE]
                this_epoch_cumul_wait += new_veh_subscriptions[cv][tc.VAR_ACCUMULATED_WAITING_TIME]
            this_epoch_result['cumulative_distance'] = this_epoch_dist
            this_epoch_result['cumulative_waiting_time'] = this_epoch_cumul_wait
            this_epoch_result['epoch'] = step
            epoch_results.append(this_epoch_result)

            # handle arriving vehicles for results recording
            arriving_vehs = traci.simulation.getArrivedIDList()
            for av in arriving_vehs:
                arrived_veh_results[av] = old_veh_subscriptions[av]
                arrived_veh_results[av]['arr_time'] = step
                arrived_veh_results[av]['dep_time'] = vehicle_departure_times[av]
                arrived_veh_results[av]['teleported'] = av in teleport_vehicles
                arrived_veh_results[av]['veh_ID'] = av

            for tl in traffic_lights:
                ryg_state = traci.trafficlight.getRedYellowGreenState(tlsID=tl)
                state_idx = traci.trafficlight.getPhase(tlsID=tl)
                state_remaining_time = (traci.trafficlight.getNextSwitch(tlsID=tl) - sim_time) / 1000
                tl_context = traci.junction.getContextSubscriptionResults(objectID=tl)

                state_counts = {}

                if signal_sync_interval is not None and step % (signal_sync_interval * tl_program_time) == 0:
                    traci.trafficlight.setPhase(tlsID=tl, index=0)
                else:
                    if tl_context is not None:
                        for veh in tl_context:
                            try:
                                if traci.vehicle.getNextTLS(vehID=veh)[0][0] == tl:
                                    # vehicle is on approach to this traffic light
                                    veh_lane = traci.vehicle.getLaneID(vehID=veh)
                                    lane_ryg_state = ryg_state[traffic_lights_lanes[tl].index(veh_lane)]
                                    state_counts[lane_ryg_state.lower()] = state_counts.get(lane_ryg_state.lower(), 0) + 1
                            except (IndexError, ValueError):
                                # vehicle is at the end of its route
                                pass
                    if 'y' not in ryg_state:
                        if state_counts.get('r', 0) >= state_counts.get('g', 0) + signal_switch_vehicles_overcome:
                            if state_remaining_time <= signal_switch_time_overcome:
                                try:
                                    traci.trafficlight.setPhase(tlsID=tl, index=state_idx + 1)
                                except traci.exceptions.TraCIException:
                                    traci.trafficlight.setPhase(tlsID=tl, index=0)

            old_veh_subscriptions = copy(new_veh_subscriptions)
            if step % write_results_interval == 0:
                write_vehicle_results(all_arrived_vehicles=arrived_veh_results,
                                      last_wrote_results_step=last_wrote_results,
                                      filename=trial_filename_vehs, header=vehicle_csv_header,
                                      header_var_dict=watching_vehicle_vars)
                write_epoch_results(all_epochs=epoch_results, last_wrote_results_step=last_wrote_results,
                                    filename=trial_filename_sim, header=simulation_csv_header)
                last_wrote_results = step

            traci.simulationStep()
            step += 1

        write_vehicle_results(all_arrived_vehicles=arrived_veh_results,
                              last_wrote_results_step=last_wrote_results,
                              filename=trial_filename_vehs, header=vehicle_csv_header,
                              header_var_dict=watching_vehicle_vars)
        write_epoch_results(all_epochs=epoch_results, last_wrote_results_step=last_wrote_results,
                            filename=trial_filename_sim, header=simulation_csv_header)
        traci.close(False)
        print("Simulation finished", trial_num)

    except BaseException as e:
        print("EXCEPTION ON PROCESS {}".format(mp.current_process().name))
        traceback.print_exc()
        return 'EXCEPTION'


def shared_results_writer(results_queue, single_result=None):
    """
    Listens for results on queue and writes to somewhere when received. Will stop with 'kill' signal written on queue.
    :param results_queue: shared queue from Multiprocessing.Manager.Queue
    :param single_result: override results queue and handle one single result
    :return: None
    """
    if single_result is not None:
        print(single_result)
        # handle single result
    else:
        print("RESULTS WRITER STARTED on process", mp.current_process().name)
        rf = open('./results/results.csv', 'a')
        rf.write("\n\n")
        rf.write(dt.datetime.now().strftime('%d/%m/%y %H:%M:%S'))
        while True:
            print("Ready for results.")
            result = results_queue.get()
            if result == 'kill' or (type(result) in (list, tuple) and 'kill' in result):
                print("Results writer killed.")
                break
            rf.write(result)
            # handle result from queue
            rf.flush()
        print("Closing results file.")
        rf.close()


if __name__ == '__main__':
    results_write_interval = 700
    simulation_config = [(adaptive_traffic_lights,
                          {'signal_switch_time_overcome': [10],
                           'signal_switch_vehicles_overcome': [10],
                           'signal_sync_interval': [None, 2.],
                           'veh_flow_scale': [2],
                           'tl_program_time': [60, 90],
                           'write_results_interval': [results_write_interval]}),
                         (random_signal_timing,
                          {'veh_flow_scale': [2],
                           'tl_program_time': [60, 90],
                           'write_results_interval': [results_write_interval]}),
                         (synchronized_signal_timing,
                          {'veh_flow_scale': [2],
                           'tl_program_time': [60, 90],
                           'write_results_interval': [results_write_interval]})
                         ]

    sim_runs = []
    for model, params in simulation_config:
        p, v = zip(*params.items())
        print(p, v)
        for vc in product(*v):
            sim_runs.append((model, {param: val for param, val in zip(p, vc)}))

    fn_matches = [re.search('[A-z]*([0-9]*)_[A-z]*.csv', fn) for fn in os.listdir('./other_results')]
    next_trial_num = max([int(tn.group(1)) for tn in fn_matches if tn is not None and tn.group(1) != ''],
                         default=0) + 1
    runs_fn = 'other_results/runs{}.txt'.format(next_trial_num)
    with open(runs_fn, 'w') as f:
        for ei, (m, p) in enumerate(sim_runs):
            f.write(str(ei + next_trial_num) + ' ' + m.__name__ + ' ' + str(p) + '\n')

    # allocate two threads per simulation instance
    # leave one whole core for system
    # process_count = mp.cpu_count() - 1          # non-hyperthreaded CPU
    process_count = int(mp.cpu_count() / 3 - 1)    # hyperthreaded CPU
    print("Using at most {} processes for simulation.".format(process_count))

    # make process ignore SIGINT before Pool is created
    # this way, child created processes inherit SIGINT handler
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    # initialize multiprocessing manager for sharing queue
    manager = mp.Manager()
    queue = manager.Queue()
    # initialize multiprocessing pool for processes
    pool = mp.Pool(min(process_count, len(sim_runs)))
    # restore SIGINT handler in parent process after Pool created
    signal.signal(signal.SIGINT, original_sigint_handler)

    try:
        # initiate shared results_writer
        # watcher = pool.apply_async(results_writer, (queue,))
        time.sleep(2)

        # initiate worker processes
        # ITERATE OVER PARAMETER CONFIGURATIONS
        jobs = []
        for sim_i, (sim_func, sim_param) in zip(range(next_trial_num, next_trial_num+len(sim_runs)), sim_runs):
            sim_param['trial_num'] = sim_i
            job = pool.apply_async(func=sim_func, kwds=sim_param)
            jobs.append((sim_i, job))
        for i, job in jobs:
            g = job.get()
            if g == 'EXCEPTION':
                print("Exception on split", i)
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt, terminating processes.")
        pool.terminate()
    else:
        try:
            queue.put('kill')
            pool.close()
        except BaseException as e:
            pass
    pool.join()


