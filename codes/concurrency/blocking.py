
import time  

def fetch_name(name, seconds):
    print(f"Start fetching the name: {name}")
    time.sleep(seconds)
    print(f"done {name}- waited {seconds} s")


start_time = time.perf_counter()
print(start_time)
fetch_name("Alice", 2)
fetch_name("Bob", 3)
fetch_name("Charlie", 1)
end_time = time.perf_counter()
print(f"Total time taken: {end_time - start_time:.2f} seconds")


