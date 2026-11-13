"""Distribute batches across isolated persistent adapter processes.

The caller starts one serial server per shard. A native crash can then end
only that shard. The regression runner retries jobs without results.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event


def run_workers(items, workers, run):
    """Call run(index, shard, cancel) once per nonempty shard, in parallel.

    Keep input order within each shard. The callback must stop its process group when cancel is set.
    """
    if workers < 1:
        raise ValueError("workers must be positive")
    if not items:
        return []
    count = min(workers, len(items))
    pool = ThreadPoolExecutor(max_workers=count, thread_name_prefix="rvw-sim")
    cancel = Event()
    try:
        futures = [pool.submit(run, n, items[n::count], cancel) for n in range(count)]
        results = [None] * count
        indexes = {future: n for n, future in enumerate(futures)}
        for future in as_completed(futures):
            results[indexes[future]] = future.result()
    except BaseException:
        cancel.set()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
        return results
