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

    if False:
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

    if False:
        adaptive = [c for c in data if c['trial_num'] == '7'][0]['veh_data']
        random = [c for c in data if c['trial_num'] == '11'][0]['veh_data']
        sync = [c for c in data if c['trial_num'] == '13'][0]['veh_data']

        adaptive_teleports = len([0 for v in adaptive if v['teleported'] == 'True'])
        random_teleports = len([0 for v in random if v['teleported'] == 'True'])
        sync_teleports = len([0 for v in sync if v['teleported'] == 'True'])

        fig, ax = plt.subplots(1, 1)
        ax.bar(np.arange(3) - 0.4, [adaptive_teleports, random_teleports, sync_teleports], width=0.8,
               color='forestgreen')
        ax.set_title("Number of teleported vehicles due to congestion")
        ax.set_xticks(np.arange(3) - 0.4)
        ax.set_xticklabels(['adaptive', 'random', 'synchronized'])
        plt.show()

        fig, axes = plt.subplots(nrows=3, ncols=2)
        adaptive_speeds = [float(v['distance']) / (int(v['arr_time']) - int(v['dep_time'])) for v in adaptive
                           if v['teleported'] == 'False']
        adaptive_waits = [float(v['total_accumulated_waiting_time']) for v in adaptive if v['teleported'] == 'False']
        random_speeds = [float(v['distance']) / (int(v['arr_time']) - int(v['dep_time'])) for v in random if
                         v['teleported'] == 'False']
        random_waits = [float(v['total_accumulated_waiting_time']) for v in random if v['teleported'] == 'False']
        sync_speeds = [float(v['distance']) / (int(v['arr_time']) - int(v['dep_time'])) for v in sync if
                       v['teleported'] == 'False']
        sync_waits = [float(v['total_accumulated_waiting_time']) for v in sync if v['teleported'] == 'False']

        max_speed = max(max(adaptive_speeds), max(random_speeds), max(sync_speeds))
        min_speed = 0
        max_wait = max(max(adaptive_waits), max(random_waits), max(sync_waits))*0.8
        min_wait = 0

        axes[0, 0].hist(adaptive_speeds, bins=100, range=(min_speed, max_speed))
        axes[0, 1].hist(adaptive_waits, bins=100, range=(min_wait, max_wait))
        axes[1, 0].hist(random_speeds, bins=100, range=(min_speed, max_speed))
        axes[1, 1].hist(random_waits, bins=100, range=(min_wait, max_wait))
        axes[2, 0].hist(sync_speeds, bins=100, range=(min_speed, max_speed))
        axes[2, 1].hist(sync_waits, bins=100, range=(min_wait, max_wait))

        axes[0, 0].set_ylim((0, 400))
        axes[0, 1].set_ylim((0, 1200))
        axes[1, 0].set_ylim((0, 400))
        axes[1, 1].set_ylim((0, 1200))
        axes[2, 0].set_ylim((0, 400))
        axes[2, 1].set_ylim((0, 1200))

        axes[0, 0].set_title("Adaptive - speed distribution")
        axes[0, 1].set_title("Adaptive - wait time distribution")
        axes[1, 0].set_title("Random - speed distribution")
        axes[1, 1].set_title("Random - wait time distribution")
        axes[2, 0].set_title("Synchronized - speed distribution")
        axes[2, 1].set_title("Synchronized - wait time distribution")

        plt.show()

    if True:
        adaptive = [c for c in data if c['trial_num'] == '7'][0]['veh_data']
        random = [c for c in data if c['trial_num'] == '11'][0]['veh_data']
        sync = [c for c in data if c['trial_num'] == '13'][0]['veh_data']

        fig, ax = plt.subplots(1, 1)
        adaptive_hist, adaptive_bins = np.histogram(np.array([float(a['arr_time']) for a in adaptive]), bins=1000)
        adaptive_hist = np.cumsum(adaptive_hist)
        random_hist, random_bins = np.histogram(np.array([float(a['arr_time']) for a in random]), bins=1000)
        random_hist = np.cumsum(random_hist)
        sync_hist, sync_bins = np.histogram(np.array([float(a['arr_time']) for a in sync]), bins=1000)
        sync_hist = np.cumsum(sync_hist)

        ax.plot(adaptive_bins[1:], adaptive_hist, label='adaptive', color='darkcyan')
        ax.plot(random_bins[1:], random_hist, label='random', color='darkmagenta')
        ax.plot(sync_bins[1:], sync_hist, label='synchronized', color='darkorange')
        ax.set_title("Cumulative number of vehicle arrivals")
        ax.set_xlabel("Epoch")
        plt.legend()
        plt.show()


