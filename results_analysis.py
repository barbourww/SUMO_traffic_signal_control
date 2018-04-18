import os
import re
import csv
from tripdataconverter import parse_trip_info
import pickle
import numpy as np
import matplotlib.pyplot as plt
import ast

results_directory = './other_results'

if 'consolidated.pkl' not in os.listdir(results_directory):
    files = [m.group() for m in [re.search(r'runs([0-9]*).txt', fn) for fn in os.listdir(results_directory)]
             if m is not None and m != '']
    output_keys = {'random': 'random', 'synchronized': 'sync', 'adaptive': 'adaptive'}

    configs = []
    for fn in files:
        with open(os.path.join(results_directory, fn), 'r') as f:
            for line in f:
                parsed = re.search(r'([0-9]*) ([A-z]*) (.*)', line)
                if parsed is not None and parsed != '':
                    c = {'trial_num': parsed.group(1),
                         'control': parsed.group(2),
                         'parameters': ast.literal_eval(parsed.group(3)),
                         'sim_file': (output_keys[parsed.group(2).split('_')[0]] + '{}_sim.csv').format(
                             parsed.group(1)),
                         'veh_file': (output_keys[parsed.group(2).split('_')[0]] + '{}_vehs.csv').format(
                             parsed.group(1)),
                         'trip_file': (output_keys[parsed.group(2).split('_')[0]] + '{}_trip_info.xml').format(
                             parsed.group(1))}
                    veh_data = []
                    with open(os.path.join(results_directory, c['veh_file']), 'r') as vf:
                        read = csv.reader(vf, delimiter=';')
                        header = read.__next__()
                        for this_line in read:
                            if len(this_line) > 0:
                                if len(this_line) < 6:
                                    print(this_line)
                                veh_data.append({k: v for k, v in zip(header, this_line)})
                                if len(veh_data[-1]) < 6:
                                    print(veh_data[-1])
                    c['veh_data'] = veh_data
                    sim_data = []
                    with open(os.path.join(results_directory, c['sim_file']), 'r') as vf:
                        read = csv.reader(vf, delimiter=';')
                        header = read.__next__()
                        for this_line in read:
                            if len(this_line) > 0:
                                sim_data.append({k: v for k, v in zip(header, this_line)})
                    c['sim_data'] = sim_data
                    c['trip_data'] = parse_trip_info(os.path.join(results_directory, c['trip_file']))
                    configs.append(c)
    with open(os.path.join(results_directory, 'consolidated.pkl'), 'wb') as f:
        pickle.dump(configs, f, protocol=2)
    data = configs
else:
    with open(os.path.join(results_directory, 'consolidated.pkl'), 'rb') as f:
        data = [c for c in pickle.load(f) if c['parameters']['veh_flow_scale'] == 1.5]
    ind = np.arange(len(data))
    width = 0.35
    fig, ax = plt.subplots(1, 1)
    axsec = ax.twinx()
    mean_speeds = []
    std_speeds = []
    mean_waits = []
    labels = []
    for config in data:
        speeds = [float(v['distance']) / (int(v['arr_time']) - int(v['dep_time'])) for v in config['veh_data'] if
                  v['teleported'] == 'False']
        m = np.mean(speeds)
        mean_speeds.append(m)
        s = np.std(speeds)
        std_speeds.append(s)
        waits = [float(v['total_accumulated_waiting_time']) for v in config['veh_data'] if v['teleported'] == 'False']
        mw = np.mean(waits)
        mean_waits.append(mw)
        sw = np.std(waits)
        print(config['trial_num'], config['control'], config['parameters'], m, s, mw, sw)
        labels.append(config['control'].split('_')[0] + '-' + str(config['parameters']['tl_program_time']) + '-' + str(config['parameters'].get('signal_sync_interval', '')))
    ax.bar(ind - width/2, mean_speeds, width, yerr=std_speeds, color='SkyBlue', label='Mean Veh Speed')
    axsec.bar(ind + width/2, mean_waits, width, color='IndianRed', label='Mean Veh Wait Time')
    ax.set_xticks(ind)
    ax.set_xticklabels(labels, rotation=45)
    ax.set_ylabel("Speed (m/s)", color='SkyBlue')
    axsec.set_ylabel("Wait time (s)", color='IndianRed')
    ax.set_title("Traffic control methodology comparison")
    plt.show()

