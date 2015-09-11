import asyncio
import functools
import requests
import aiohttp
import sys


@asyncio.coroutine
def worker(get, queue: asyncio.JoinableQueue, output):
    while True:
        item = yield from queue.get()
        # This is horrible and I feel bad for writing it, believe me
        try:
            if item is None:
                return

            chunks, id = item

            for i in range(id, id+chunks):
                try:
                    data = yield from get("item/{}".format(id))
                    output(data)
                except Exception:
                    pass
        except Exception as e:
            pass
        finally:
            queue.task_done()


class Monitor(object):
    def __init__(self, max_id, from_id, req_limit, output):
        self.output = output
        self.requests = 0
        self.errors = 0
        self._stopped = False
        self.semaphore = asyncio.Semaphore(req_limit)

        self.from_id = from_id
        self.max_id = max_id

    def stop(self):
        self._stopped = True

    def error(self, id, ex):
        self.errors += 1
        self.output.write("Error @ {id}: {ex}\n".format(id=id, ex=ex))

    @asyncio.coroutine
    def start(self):
        prev_req, prev_err = 0, 0

        while not self._stopped:
            yield from asyncio.sleep(1)
            current_req, current_err = self.requests, self.errors
            diff_req, diff_err = current_req - prev_req, current_err - prev_err
            prev_req, prev_err = current_req, current_err

            current_id = self.from_id + self.requests

            percentage = (current_id / self.max_id) * 100

            self.output.write(
                "[{percentage:3.0f}%] Requests: {reqs}\tErrors: {errors}\t{current}/{max}\t{left}\n".format(
                    percentage=percentage,
                    reqs=diff_req,
                    errors=diff_err,
                    current=current_id,
                    max=self.max_id,
                    left=self.max_id - current_id))
            self.output.flush()


@asyncio.coroutine
def get_items(data_types, output, to_id, from_id, max_requests):
    def _output(data):
        if filter_item(data_types, data):
            output(data)

    if from_id is None:
        from_id = 1

    monitor = Monitor(to_id, from_id, max_requests, sys.stderr)

    get = functools.partial(_get, monitor)

    queue = asyncio.JoinableQueue(maxsize=max_requests)
    workers = [asyncio.async(worker(get, queue, _output)) for i in range(max_requests)]
    monitor_task = asyncio.async(monitor.start())

    chunks = 10

    for i in range(from_id, to_id, chunks):
        yield from queue.put((chunks, i))

    for worker_future in workers:
        yield from queue.put(None)

    yield from queue.join()
    monitor.stop()
    yield from monitor_task


@asyncio.coroutine
def _get(monitor, name):
    with (yield from monitor.semaphore):
        monitor.requests += 1
        try:
            req = yield from aiohttp.get("https://hacker-news.firebaseio.com/v0/{0}.json".format(name))
            data = yield from req.json()
            if data is None or "id" not in data:
                raise Exception("Data is empty or has no id attribute!")
            return data
        except Exception as ex:
            monitor.error(name, ex)


def filter_item(data_types, item):
    all = "all" in data_types
    if "type" not in item:
        if all or "users" in data_types:
            return True
    elif all or item["type"] in data_types:
        return True
