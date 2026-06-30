"""
What is a thread? — runnable companion to concurrency/01_what_is_a_thread.qmd

Run with:  python thread.py

Demonstrates, in order:
  1. You are ALREADY in a thread (the main thread) before creating any.
  2. A worker thread is a distinct, OS-scheduled entity (it has its own id).
  3. The private/shared split: a local lives on a thread's PRIVATE stack;
     a global object lives on the SHARED heap and every thread can change it.
  4. A thread's life through Running and Blocked, timed with perf_counter
     (the monotonic clock — used here because we measure ELAPSED durations).
"""

import threading
import time


# ---------------------------------------------------------------------------
# 1. You are already in a thread
# ---------------------------------------------------------------------------
def show_starting_threads():
    current = threading.current_thread()
    print(f"I am running in : {current.name}")
    print(f"Live threads    : {threading.active_count()} "
          f"-> {[t.name for t in threading.enumerate()]}")


# ---------------------------------------------------------------------------
# 2. A worker is a distinct schedulable entity
# ---------------------------------------------------------------------------
def worker():
    me = threading.current_thread()
    # me.ident is the OS-level thread id: proof this is its own thread.
    print(f"  [{me.name}] running  (os thread id = {me.ident})")


# ---------------------------------------------------------------------------
# 3. Private stack vs shared heap
# ---------------------------------------------------------------------------
shared_counter = {"value": 0}          # one object on the SHARED heap


def add_some(label, how_many):
    local_tally = 0                    # lives on THIS thread's PRIVATE stack
    for _ in range(how_many):
        local_tally += 1
        shared_counter["value"] += 1   # reaches into the SHARED object
    print(f"  [{label}] my private tally = {local_tally} (own stack)")


# ---------------------------------------------------------------------------
# 4. A thread's life: Running -> Blocked -> Running, timed
# ---------------------------------------------------------------------------
START = time.perf_counter()
events = []                            # (name, state, t_enter, t_leave)
events_lock = threading.Lock()         # guard the shared list (it's on the heap!)


def record(name, state, t0, t1):
    with events_lock:
        events.append((name, state, t0 - START, t1 - START))


def life_of_a_thread(name, work_before, wait, work_after):
    t0 = time.perf_counter()
    sum(i * i for i in range(work_before))            # RUNNING
    t1 = time.perf_counter(); record(name, "Running", t0, t1)

    t0 = time.perf_counter()
    time.sleep(wait)                                  # BLOCKED (voluntary wait)
    t1 = time.perf_counter(); record(name, "Blocked", t0, t1)

    t0 = time.perf_counter()
    sum(i * i for i in range(work_after))             # RUNNING again
    t1 = time.perf_counter(); record(name, "Running", t0, t1)


if __name__ == "__main__":
    print("== 1. starting threads ==")
    show_starting_threads()

    print("\n== 2. a worker thread ==")
    helper = threading.Thread(target=worker, name="Worker-1")
    helper.start()        # Ready -> the scheduler runs it
    helper.join()         # main thread BLOCKS here until Worker-1 returns

    print("\n== 3. private stack vs shared heap ==")
    threads = [
        threading.Thread(target=add_some, args=("A", 1000)),
        threading.Thread(target=add_some, args=("B", 1000)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  shared_counter seen by all = {shared_counter['value']}")

    print("\n== 4. a thread's life, timed ==")
    threads = [
        threading.Thread(target=life_of_a_thread, args=("T1", 200_000, 0.15, 120_000)),
        threading.Thread(target=life_of_a_thread, args=("T2", 120_000, 0.10, 200_000)),
        threading.Thread(target=life_of_a_thread, args=("T3", 160_000, 0.20, 160_000)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()
    for name, state, a, b in sorted(events, key=lambda e: e[2]):
        print(f"  {name}  {state:8s}  {a * 1000:6.1f} ms -> {b * 1000:6.1f} ms")
