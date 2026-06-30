import threading 
import time 

shared_counter = {"value":0}

def add_some(label, how_many):
    local_tally = 0
    for _ in range(how_many):
        local_tally += 1
        shared_counter["value"] += 1 

    print(f"[{label}] my private tally = {local_tally} (lived on my stack)")

threads = [threading.Thread(target=add_some, args=("A", 1000), name = "Worker-1"), threading.Thread(target=add_some, args=("B", 1000), name = "Worker-2")]

for t in threads :
    t.start()
for t in threads :
    t.join()

print(f"shared counter seen by all threads = {shared_counter['value']} (lived on the heap)")





