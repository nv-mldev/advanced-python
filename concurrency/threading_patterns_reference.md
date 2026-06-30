# Threading patterns in Python — a reference

> **Status:** standalone reference, *not yet* wired into `_quarto.yml`. Several
> patterns below use locks, thread-safe queues, and `Event` — primitives the
> book's "What is a thread?" chapter forward-references as *upcoming* chapters.
> When those exist, this doc splits cleanly into properly-sequenced chapters.
> For now it's a working catalogue you can read and copy from.

Every pattern here is a different answer to one of three needs:

1. **Run work concurrently** (overlap I/O waits) — patterns 1–3.
2. **Share state safely** (don't corrupt the heap) — patterns 4–8.
3. **Coordinate / shut down cleanly** (signal, limit, sequence, stop) — patterns 9–13.

The single rule underneath all of them: **threads share the heap, so any data two
threads both touch needs protection — and threads only help with *I/O-bound* work,
not CPU-bound work (the GIL).**

---

## 0. The decision, first

Before reaching for a pattern, place your work:

| Your work is… | Use | Why |
|---|---|---|
| **I/O-bound**, a handful of tasks | bare `Thread` (pattern 1) | simple, waits overlap |
| **I/O-bound**, many tasks / repeated | `ThreadPoolExecutor` (pattern 2) | reuse threads, get results back |
| **Streaming / pipeline** between threads | `queue.Queue` (pattern 3) | the thread-safe hand-off |
| **CPU-bound** (image math, crunching) | **processes**, not threads | the GIL blocks parallel Python |
| **Blocking call inside `async` code** | `asyncio.to_thread` (pattern 13) | keep the event loop unblocked |

If the work is CPU-bound, stop — switch to `multiprocessing` / `ProcessPoolExecutor`.
No threading pattern beats the GIL for pure-Python compute.

---

## 1. Thread-per-task (fire, then join)

The most basic pattern: spin a thread per job, start them all, then wait. Good for
a *small, fixed* number of independent I/O waits.

```python
import threading

def fetch(url):
    ...  # some blocking I/O

threads = [threading.Thread(target=fetch, args=(u,)) for u in urls]
for t in threads:           # start all → their waits now overlap
    t.start()
for t in threads:           # block here until every one finishes
    t.join()
```

- **Strength:** dead simple.
- **Weakness:** no result handling, no limit on thread count, manual bookkeeping.
  For anything beyond a few tasks, use a pool (pattern 2).

---

## 2. Worker pool — `ThreadPoolExecutor` (the modern default)

`concurrent.futures.ThreadPoolExecutor` reuses a fixed set of threads and hands you
back **results** (or exceptions) via `Future` objects. This is what you should reach
for most of the time.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch(url):
    return len(url)         # pretend this does blocking I/O and returns a result

with ThreadPoolExecutor(max_workers=8) as pool:
    # map: results come back IN INPUT ORDER, like a parallel map()
    for url, size in zip(urls, pool.map(fetch, urls)):
        print(url, size)

    # submit + as_completed: results come back AS THEY FINISH (fastest first)
    futures = {pool.submit(fetch, u): u for u in urls}
    for fut in as_completed(futures):
        url = futures[fut]
        try:
            print(url, fut.result())     # .result() re-raises any exception
        except Exception as exc:
            print(url, "failed:", exc)
# leaving the `with` block waits for all tasks and shuts the pool down
```

- **`map`** when you want results in order and don't need per-task error handling.
- **`submit` + `as_completed`** when you want to react as each finishes, or handle
  failures individually.
- **`max_workers`** caps concurrency — also the simplest way to rate-limit I/O.
- Exceptions are captured in the `Future` and re-raised when you call `.result()`,
  so they don't silently vanish (a real risk with bare threads).

---

## 3. Producer–Consumer — `queue.Queue` (the workhorse)

One or more threads *produce* items; one or more *consume* them. `queue.Queue` is
**already thread-safe** — it has the locking built in, so you never write a lock
yourself for the hand-off. This is the backbone of most real threaded systems
(including a producer thread feeding a pool of worker threads).

```python
import queue, threading

work = queue.Queue(maxsize=100)   # maxsize → backpressure: producer blocks if full
SENTINEL = object()               # a unique "no more work" marker

def producer():
    for item in source():
        work.put(item)            # blocks if the queue is full
    work.put(SENTINEL)            # tell the consumer we're done

def consumer():
    while True:
        item = work.get()         # blocks until something is available
        if item is SENTINEL:
            work.task_done()
            break
        handle(item)
        work.task_done()          # mark this item processed

threading.Thread(target=producer).start()
threading.Thread(target=consumer).start()
work.join()                       # blocks until every put() has a matching task_done()
```

- **`maxsize` gives you backpressure** — a fast producer can't run memory away from
  a slow consumer; it blocks instead. Crucial for high-rate streaming feeds.
- **The sentinel pattern** is how you signal "done" cleanly. For *N* consumers, put
  *N* sentinels.
- **`task_done()` / `join()`** let the main thread wait for the *work* to drain,
  separate from waiting for *threads* to exit.
- This is the FIFO cousin of the LIFO call stack — items come out in the order they
  went in.

---

## 4. Protecting shared state — `Lock`

The moment two threads modify the same heap object, you have a **race condition**:
`counter += 1` is *read, add, write* — three steps the OS can interrupt between, so
two threads can both read the same old value and one increment is lost. A `Lock`
makes a section **mutually exclusive** — only one thread inside at a time.

```python
import threading

counter = 0
lock = threading.Lock()

def increment():
    global counter
    for _ in range(100_000):
        with lock:              # acquire on enter, release on exit (even on error)
            counter += 1        # now atomic w.r.t. other threads holding `lock`
```

- **Always use `with lock:`** rather than manual `acquire()`/`release()` — it releases
  even if the body raises.
- **Hold the lock as briefly as possible** — only around the shared access. Long
  critical sections serialize your threads and kill the concurrency you wanted.
- **The lock protects a *discipline*, not the data itself.** Every thread touching
  the shared data must use the *same* lock; one thread skipping it reopens the race.

---

## 5. `RLock` — when the same thread must re-acquire

A plain `Lock` deadlocks if the *same* thread tries to acquire it twice (e.g. a
locked method that calls another locked method). `RLock` (reentrant lock) lets the
**owning** thread acquire it repeatedly, releasing fully only when balanced.

```python
import threading

class Account:
    def __init__(self):
        self._lock = threading.RLock()
        self._balance = 0

    def deposit(self, amount):
        with self._lock:
            self._balance += amount

    def transfer(self, other, amount):
        with self._lock:            # holds _lock...
            self.deposit(-amount)   # ...and deposit() acquires it AGAIN — fine with RLock
            other.deposit(amount)
```

Use `RLock` when a guarded method may call another guarded method on the same object.
If you never re-enter, prefer plain `Lock` (cheaper and harder to misuse).

---

## 6. Signaling — `Event` and `Condition`

**`Event`** is a one-bit flag threads can wait on: "has *this* happened yet?" Perfect
for *start* and *stop* signals.

```python
import threading

ready = threading.Event()

def worker():
    ready.wait()             # blocks until someone sets the event
    print("go!")

threading.Thread(target=worker).start()
...                          # do setup
ready.set()                  # release every thread waiting on `ready`
```

**`Condition`** is for "wait until some *state* is true, then act," when an `Event`'s
single flag isn't enough (e.g. "wait until the buffer has at least 3 items"). It pairs
a lock with `wait()` / `notify()`.

```python
import threading

cond = threading.Condition()
items = []

def consumer():
    with cond:
        cond.wait_for(lambda: len(items) >= 3)   # releases the lock while waiting
        chunk, items[:] = items[:3], items[3:]
    process(chunk)

def producer(x):
    with cond:
        items.append(x)
        cond.notify()        # wake a waiter to re-check its condition
```

Rule of thumb: **`Event` for a binary "did X happen", `Condition` for "wait until a
predicate over shared state holds".** For simple producer/consumer, prefer `queue.Queue`
(pattern 3) — it's a `Condition` already wrapped up correctly.

---

## 7. Limiting concurrency — `Semaphore`

A `Semaphore` allows up to *N* threads through at once — a counted lock. Use it to cap
a *scarce resource*: simultaneous connections, GPU slots, open file handles.

```python
import threading

gpu_slots = threading.Semaphore(2)   # at most 2 threads run inference at once

def infer(batch):
    with gpu_slots:                  # blocks if 2 are already inside
        run_on_gpu(batch)
```

(`BoundedSemaphore` additionally errors if you release more than you acquired —
catches a common bug. A `ThreadPoolExecutor(max_workers=N)` is often a cleaner way to
get the same cap; reach for `Semaphore` when the limited resource is narrower than the
whole task.)

---

## 8. Per-thread state — `threading.local`

Sometimes you want data that's **global in name but private per thread** — e.g. a
database connection or HTTP session each thread should have its own of, never shared.
`threading.local()` gives each thread its own copy of the attributes.

```python
import threading

_state = threading.local()

def get_connection():
    if not hasattr(_state, "conn"):
        _state.conn = open_connection()   # created once per thread, lazily
    return _state.conn                     # each thread sees only its own
```

This sidesteps locking entirely for that data: if it's never shared, it can't race.
The "shared kitchen, private notebook" idea from the chapter, made explicit in code.

---

## 9. Background worker with graceful shutdown (`daemon` + `Event`)

A long-running background thread (a poller, a heartbeat) that the main program can
ask to **stop cleanly**. The `Event` is the off-switch; a `daemon=True` thread won't
keep the process alive on exit, but graceful stop is still better than abrupt kill.

```python
import threading, time

stop = threading.Event()

def background_loop():
    while not stop.is_set():
        do_one_cycle()
        stop.wait(timeout=1.0)   # sleeps up to 1s BUT wakes instantly on stop.set()

t = threading.Thread(target=background_loop, daemon=True)
t.start()
...
stop.set()                       # ask it to finish the current cycle and exit
t.join(timeout=5)                # give it a moment to wind down
```

- **`stop.wait(timeout=...)` instead of `time.sleep(...)`** — the thread reacts to the
  stop signal *immediately* instead of finishing a full sleep. This one swap is the
  difference between a 1-second and a 5-minute shutdown for slow loops.
- **`daemon=True`** is a safety net (process can exit even if this thread is stuck),
  not a substitute for real shutdown logic.

---

## 10. Periodic task — `threading.Timer`

Run something once after a delay, or (by rescheduling) on a repeating tick.

```python
import threading

def heartbeat():
    ping()
    threading.Timer(5.0, heartbeat).start()   # reschedule self every 5s

threading.Timer(5.0, heartbeat).start()
```

Fine for light, occasional jobs. For anything heavy or high-frequency, use the
background-loop pattern (9) instead — each `Timer` spawns a fresh thread, which adds up.

---

## 11. Phase synchronization — `Barrier`

A `Barrier(n)` makes *n* threads each wait until **all n** have arrived, then releases
them together. Useful for staged/parallel algorithms: everyone finishes phase 1 before
anyone starts phase 2.

```python
import threading

barrier = threading.Barrier(3)

def worker(i):
    load_partition(i)
    barrier.wait()        # no one proceeds until all 3 have loaded
    process_partition(i)  # all start phase 2 together
```

---

## 12. Result-gathering (`Future`) — when you launch now, need the answer later

`ThreadPoolExecutor.submit()` returns a `Future` immediately; you do other work, then
collect the result when you need it. This decouples *launching* from *collecting*.

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor() as pool:
    future = pool.submit(slow_lookup, key)   # starts now, returns at once
    do_other_setup()                         # overlaps with the lookup
    value = future.result()                  # block here only when you truly need it
```

---

## 13. Bridging threads and `async` — `asyncio.to_thread`

An `async` event loop must **never** run a blocking call directly (it freezes every
task). When you *must* call blocking code (a synchronous database driver, a legacy
library, a slow `requests` call) from async code, push it onto a thread so the loop
stays free:

```python
import asyncio

async def handler():
    # blocking_query() is synchronous — run it in a worker thread so the
    # event loop keeps serving other connections meanwhile
    value = await asyncio.to_thread(blocking_query, key="status")
    await send(value)
```

`asyncio.to_thread` (Python 3.9+) runs the function in the default thread pool and
`await`s its result — blocking work overlaps with the loop instead of stalling it.
(Pre-3.9: `loop.run_in_executor(None, fn, *args)`.) This is *exactly* why threads and
async aren't rivals: async handles the many waits, threads absorb the occasional
unavoidable blocking call.

---

## Cross-cutting cautions

- **Don't share without protection.** Any heap object two threads write needs a lock
  (4) or a thread-safe handoff (`queue.Queue`, 3). Reads-only is fine; read-modify-write
  is not.
- **Lock ordering prevents deadlock.** If threads grab multiple locks, *always acquire
  them in the same global order*. A→B in one thread and B→A in another is the classic
  deadlock.
- **Threads don't speed up CPU-bound Python.** The GIL serializes bytecode. Measure;
  if it's compute, use processes.
- **Exceptions in bare threads vanish.** A `target` that raises just dies silently.
  Pools (2) capture exceptions in the `Future`; bare threads need your own try/except
  + reporting.
- **Prefer the highest-level tool that fits:** `ThreadPoolExecutor` over manual threads,
  `queue.Queue` over hand-rolled lock+list, `to_thread` over manual executor plumbing.

---

## Mapping to the running example

- **Producer → worker pool**: producer–consumer over a bounded `queue.Queue` (3), with
  `Event`-based graceful shutdown (9). Backpressure (`maxsize`) stops a fast producer
  from outrunning slow consumers.
- **A blocking call inside the async streaming server**: never inline — `asyncio.to_thread`
  (13), or isolate the blocking work in a separate process entirely.
- **Limiting concurrent heavy work** (e.g. CPU/GPU-bound processing): a `Semaphore` (7)
  or a small-`max_workers` `ThreadPoolExecutor` (2).
- **Limiting simultaneous GPU inference**: `Semaphore` (7) or a small-`max_workers`
  pool (2).
```
