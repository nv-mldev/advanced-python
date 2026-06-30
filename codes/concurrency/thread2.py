import threading 
import time 

# current = threading.current_thread()
# print(f" I am running in {current.name} thread")
# print(f"Live threads running right now: {threading.active_count()} threads")
# print(f"List of all threads running right now: {[t.name for t in threading.enumerate()]} threads")


def my_worker(label):
    me = threading.current_thread()
    print(f"[{me.name} running  job {label} (os thread id = {me.ident}) ]")


print(f"before: {threading.active_count()} threads")

helper = threading.Thread(target=my_worker, args=("first-job",), name = "Worker-1")
helper.start()
helper.join()

print(f"after: {threading.active_count()} threads")



