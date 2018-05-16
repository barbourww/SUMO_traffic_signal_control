README.txt for SUMO Traffic Signal Control project
William Barbour, Alex Browne, Grant Poe

Primary simulation file: 
------------------------
## parallel_sumo.py ##
- initiates SUMO simulations under any of three scenarios (uncoordinated/random, synchronized, and adaptive signalling)
- handles adaptive signalling logic via real-time control of SUMO simulation with TraCI interface
- allows for simulation parameters to be explored via grid search across each scenario
- parallelizes simulations, each with new SUMO instance, for greater computational capability
- writes results to file (CSV format) for simulation epochs and vehicle variables

Auxillary files:
----------------
# network_parse.py
- creates vehicle route configuration files with given volumes between terminal nodes on perimeter of network

# randomize_tl_offset.py
- creates network configuration files for uncoordinated signaling scheme

# synchronize_tl.py
- creates network configuration files for synchronized signaling scheme

# results_analysis.py
- primary results parsing and analysis methods

# tripdataconverter.py
- parsing function for SUMO-generated trip data files (XML format)