import multiprocessing as mp
import signal
import traceback
import os
import csv
import datetime as dt
import time
import sys

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


def simulation(simulation_parameters):
    try:
        print("Simulation on process {}".format(mp.current_process().name))
        traci.start(sumoCmd)
        for i in range(50):
            print("Step {}".format(i))
            traci.simulationStep()
        traci.close(wait=False)
    except BaseException as e:
        print("EXCEPTION ON PROCESS {}".format(mp.current_process().name))
        traceback.print_exc()
        return 'EXCEPTION'


def save_results(results, header, filename):
    with open(os.path.join('results/', filename), 'w') as f:
        csvw = csv.writer(f, delimeter=';', quoting=csv.QUOTE_NONE)
        csvw.writerow(header)
        for row in results:
            csvw.writerow(row=row)


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
    # allocate two threads per simulation instance
    # leave one whole core for system
    process_count = mp.cpu_count() - 1          # non-hyperthreaded CPU
    # process_count = mp.cpu_count() / 2 - 1    # hyperthreaded CPU
    print("Using at most {} processes for simulation.".format(process_count))

    # make process ignore SIGINT before Pool is created
    # this way, child created processes inherit SIGINT handler
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    # initialize multiprocessing manager for sharing queue
    manager = mp.Manager()
    queue = manager.Queue()
    # initialize multiprocessing pool for processes
    pool = mp.Pool(process_count)
    # restore SIGINT handler in parent process after Pool created
    signal.signal(signal.SIGINT, original_sigint_handler)

    simulation_config = [1, 2]

    try:
        # initiate shared results_writer
        # watcher = pool.apply_async(results_writer, (queue,))
        time.sleep(2)

        # initiate worker processes
        # ITERATE OVER PARAMETER CONFIGURATIONS
        jobs = []
        for i, sim_param in enumerate(simulation_config):
            job = pool.apply_async(simulation, (sim_param,))
            jobs.append((i, job))
        for i, job in jobs:
            g = job.get()
            if g == 'EXCEPTION':
                print("Exception on split", i)
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt, terminating processes.")
        pool.terminate()
    else:
        queue.put(('kill', 'kill'))
        pool.close()
    pool.join()


