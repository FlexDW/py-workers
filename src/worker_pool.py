"""
This module provides tools for managing asynchronous tasks with concurrency and rate limits.
It includes a Task definition for scheduled execution and a WorkerPool to manage multiple tasks using asyncio.

Classes:
    Task: Defines a function to be executed asynchronously, with optional timeout and retry settings.
    WorkerPool: Manages a pool of tasks, enforcing concurrency and rate limits.
"""

__all__ = ["worker_pool", "WorkerPool"]

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from math import ceil
import random
from typing import Any, Awaitable, Callable, Deque, List, NamedTuple, Optional


class Task(NamedTuple):
    fn: Callable[[], Awaitable[Any]]
    timeout: int | None = None
    retries: int = 0
    retryable_exceptions: List[type[Exception]] = [Exception]
    backoff: Callable[[int], float] = lambda attempts: 2**attempts + random.uniform(0, 1)


class DelayedTask:
    task: Task
    future: asyncio.Future

    def __init__(self, task: Task):
        self.task = task
        self.future = asyncio.Future()
        self.attempts = 0

    async def execute(self, callback: Optional[Callable[[], None]] = None):
        try:
            while True:
                try:
                    if self.task.timeout:
                        result = await asyncio.wait_for(self.task.fn(), self.task.timeout)
                    else:
                        result = await self.task.fn()

                    self.future.set_result(result)
                    break
                except Exception as e:
                    if not any(isinstance(e, exc) for exc in self.task.retryable_exceptions):
                        self.future.set_exception(e)
                        break
                    self.attempts += 1
                    if self.attempts >= self.task.retries:
                        self.future.set_exception(e)
                        break
                    await asyncio.sleep(self.task.backoff(self.attempts))
        finally:
            if callback:
                callback()

class Semaphore:
    value: int | None
    semaphore: asyncio.Semaphore | None

    def __init__(self, value: int | None):
        self.value = value
        if value:
            self.semaphore = asyncio.Semaphore(value)

    async def acquire(self):
        if self.value:
            return await self.semaphore.acquire()

    def release(self):
        if self.value:
            return self.semaphore.release()

class WorkerPool:
    size: int | None
    rate: float | None
    count: int

    def __init__(self, size: int | None = None, rate: float | None = None):
        """
        Initializes a new WorkerPool class. Params size, rate or both must be provided.

        :param
            size: specifies the maximum number of concurrent workers that can be executing
                tasks. If None or not provided, no limit will be set.

            rate: specifies the maximum number of executions per second. If None or not
                provided, the rate is unbounded.

        Example usage:
            workers = WorkerPool(size=5, rate=10)
            # This creates a WorkerPool that allows up to 5 concurrent workers,
            # with a maximum rate of 10 executions per second.
        """

        if size and (size <= 0 or round(size) != size):
            raise ValueError("Size must be a positive integer or None.")
        if rate and rate <= 0:
            raise ValueError("Rate must be a positive float or None.")

        self.size = size
        self.rate = rate
        self.count = 0
        self._queue: Deque[DelayedTask] = deque()
        self._accepting = True
        self._shutdown = False

        self._semaphore = Semaphore(ceil(self.rate) if self.rate else None) # ceil: still need capcaity for partial (e.g. 0.5)
        self._wait = 1 / self.rate if self.rate else 0

        if self.rate:
            self.release_future = asyncio.create_task(
                self._release(),
                name=f'{self.__class__.__name__}.{self._release.__name__}'
            )

    def _put_task(self, task: DelayedTask):
        self._queue.append(task)

    def _mark_done(self):
        self.count -= 1
        asyncio.create_task(self._next())

    async def _release(self):
        # only ever called once, at initialization
        while not self._shutdown:
            await asyncio.sleep(self._wait)
            self._semaphore.release()

    async def _next(self):
        if not self._shutdown and (self.size is None or self.count < self.size):
            if self._queue:
                self.count += 1
                task = self._queue.popleft()
                await self._semaphore.acquire()
                await task.execute(self._mark_done)

    def run(
        self,
        task: Callable[[], Awaitable[Any]],
        timeout: int | None = None,
        retries: int = 0,
        retryable_exceptions: List[type[Exception]] = [Exception],
        backoff: Callable[[int], float] = lambda attempts: 2**attempts + random.uniform(0, 1),
        ):
        """
        Schedules a new task for execution. The task will be executed asynchronously, with optional
        timeout and retry settings.

        :param
            task: the function to be executed asynchronously. This function should be a coroutine, not
                take any arguments, and return the result of the task.
            timeout: the maximum number of seconds to wait for the task to complete. If None or not
                provided, the task will not have a timeout.
            retries: the maximum number of times to retry the task if it fails. If 0 or not provided,
                the task will not be retried.
            retryable_exceptions: a list of exceptions that should trigger a retry. If not provided,
                all exceptions will trigger a retry.
            backoff: a function that takes the number of attempts and returns the number of seconds to
                wait before the next attempt. If not provided, the default backoff strategy will be used:
                2^attempts + random.uniform(0, 1).
        """
        if not self._accepting:
            raise RuntimeError("WorkerPool has shutdown and not accepting new tasks.")

        task = Task(task, timeout, retries, retryable_exceptions, backoff)
        delayed_task = DelayedTask(task)
        self._put_task(delayed_task)
        asyncio.create_task(self._next())
        return delayed_task.future

    async def shutdown(self):
        self._accepting = False
        await asyncio.gather(*[task.future for task in self._queue])
        self._shutdown = True
        if self.rate:
            self.release_future.cancel()

    async def kill(self):
        self._accepting = False
        self._shutdown = True
        if self.rate:
            self.release_future.cancel()
        while self._queue:
            task = self._queue.popleft()
            task.future.set_exception(asyncio.CancelledError("WorkerPool shutdown"))

@asynccontextmanager
async def worker_pool(size: int | None = None, rate: float | None = None):
    try:
        workers = WorkerPool(size, rate)
        yield workers
    finally:
        await workers.shutdown()
