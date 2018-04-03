import os
import sys

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("SUMO_HOME not in system environment variables. Please declare variable.")

sumoBinaryCMD = "C:/Program Files (x86)/DLR/Sumo/bin/sumo.exe"
sumoBinaryGUI = "C:/Program Files (x86)/DLR/Sumo/bin/sumo-gui.exe"

sumoCmd = [sumoBinaryGUI, "-c", "./nyc.sumocfg"]

import traci
import traci.constants as tc
traci.start(sumoCmd)
print("Simulation loaded.")
junc = "42435645"
traci.junction.subscribeContext(objectID=junc, domain=tc.CMD_GET_VEHICLE_VARIABLE,
                                  dist=40, varIDs=[tc.VAR_SPEED, tc.VAR_WAITING_TIME])
print(traci.junction.getContextSubscriptionResults(objectID=junc))
step = 0
while step < 50:
    print("Step", step)
    traci.simulationStep()
    print(traci.junction.getContextSubscriptionResults(objectID=junc))
    step += 1
traci.close(False)
