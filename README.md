# Advanced Python Programming

A growing book on **how Python actually runs** and **how programs do many things at once**
(threads, processes, async) — built with [Quarto](https://quarto.org). Each chapter goes
*intuition → mechanics → runnable code → visualization*, and the Python cells are executed
when the book is built, so the printed output is real.

## Parts

- **Python Foundations** — how Python runs a program: source → bytecode → the interpreter
  loop, the call stack of frames, the heap, names as references, and memory management.
- **Concurrency — Threads in Depth** — from first principles to expert, one primitive at a
  time (threads, the `Thread` class, race conditions, locks, … more in progress), tied
  together by one running example: a producer → bounded queue → worker pool → socket-stream
  pipeline.

## Build locally

```bash
uv venv .venv && uv pip install -r requirements.txt   # one-time setup
quarto preview      # live local preview
quarto render       # build the static site into _book/
```

## Publish

```bash
quarto publish quarto-pub
```
