from unittest.mock import Mock
import asyncio
import time
import pytest
from werkpool import WorkerPool, worker_pool, Task, DelayedTask

class TestDelayedTask:
    @pytest.mark.asyncio
    async def test_successful_task_execution(self):
        async def simple_task():
            return "Success"

        task = Task(fn=simple_task)
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        result = await delayed_task.future
        assert result == "Success"

    @pytest.mark.asyncio
    async def test_successful_task_execution_with_callback(self):
        async def simple_task():
            return "Success"

        callback = Mock()
        task = Task(fn=simple_task)
        delayed_task = DelayedTask(task)
        await delayed_task.execute(callback)
        await delayed_task.future
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_with_non_retryable_exception(self):
        async def faulty_task():
            raise ValueError("An error occurred")

        task = Task(fn=faulty_task, retryable_exceptions=(KeyError,))
        delayed_task = DelayedTask(task)
        with pytest.raises(ValueError):
            await delayed_task.execute()
            await delayed_task.future

    @pytest.mark.asyncio
    async def test_task_with_multiple_retryable_exception_types(self):
        attempts = 0

        async def occasionally_faulty_task():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("Timeout")
            elif attempts == 2:
                raise ConnectionError("Connection error")
            return "Recovered"

        task = Task(fn=occasionally_faulty_task, retries=3, retryable_exceptions=(TimeoutError, ConnectionError))
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        result = await delayed_task.future
        assert result == "Recovered"


    @pytest.mark.asyncio
    async def test_task_with_retryable_exception(self):
        attempts = 0

        async def occasionally_faulty_task():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise TimeoutError("Timeout")
            return "Recovered"

        task = Task(fn=occasionally_faulty_task, retries=3, retryable_exceptions=(TimeoutError,))
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        result = await delayed_task.future
        assert result == "Recovered"

    @pytest.mark.asyncio
    async def test_task_with_multiple_retryable_exception_types(self):
        attempts = 0

        async def occasionally_faulty_task():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("Timeout")
            elif attempts == 2:
                raise ConnectionError("Connection error")
            return "Recovered"

        task = Task(fn=occasionally_faulty_task, retries=3, retryable_exceptions=(TimeoutError, ConnectionError))
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        result = await delayed_task.future
        assert result == "Recovered"

    @pytest.mark.asyncio
    async def test_task_with_retries_backoff_called_with_attempts(self):
        attempts = 0

        async def occasionally_faulty_task():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise TimeoutError("Timeout")
            return "Recovered"

        backoff = Mock()
        backoff.return_value = 1

        task = Task(fn=occasionally_faulty_task, retries=3, retryable_exceptions=(TimeoutError,), backoff=backoff)
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        await delayed_task.future
        backoff.assert_called_once()
        backoff.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_task_with_too_many_retries(self):
        async def faulty_task():
            raise TimeoutError("Timeout")

        task = Task(fn=faulty_task, retries=3, retryable_exceptions=(TimeoutError,))
        delayed_task = DelayedTask(task)
        with pytest.raises(TimeoutError):
            await delayed_task.execute()
            await delayed_task.future

class TestWorkerPool:
    @pytest.mark.asyncio
    async def test_worker_pool_run(self):
        async def simple_task():
            return 42

        async with worker_pool(size=1) as pool:
            result = await pool.run(simple_task)
            assert result == 42

    @pytest.mark.asyncio
    async def test_worker_size_limits_concurrent_workers(self):
        size = 5
        num_tasks = 10
        task_duration = 1

        async def slow_task():
            await asyncio.sleep(task_duration)

        start_time = time.time()
        async with worker_pool(size) as pool:
            results = []
            for _ in range(num_tasks):
                results.append(pool.run(slow_task))
            await asyncio.gather(*results)
        end_time = time.time()

        total_time = end_time - start_time
        expected_time = (num_tasks / size) * task_duration
        assert total_time >= expected_time, f"Tasks completed faster than expected, {total_time} < {expected_time}"
        assert total_time <= expected_time * 1.05, f"Tasks took too long to complete, {total_time} > {expected_time}"

    @pytest.mark.asyncio
    async def test_worker_rate_limits_freq(self):
        num_tasks = 10
        task_duration = 1
        rate = 2

        async def slow_task():
            print("############## Task started ##############")
            await asyncio.sleep(task_duration)

        start_time = time.time()
        async with worker_pool(rate=rate) as pool:
            results = []
            for _ in range(num_tasks):
                print("############## Running a task ##############")
                results.append(pool.run(slow_task))

            print("############## awaiting all ##############")
            await asyncio.gather(*results)
            print("############## awaited all ##############")

        end_time = time.time()

        total_time = end_time - start_time
        expected_time = num_tasks / rate
        assert total_time >= expected_time, f"Tasks completed faster than expected, {total_time} < {expected_time}"
        assert total_time <= expected_time * 1.05, f"Tasks took too long to complete, {total_time} > {expected_time}"

    @pytest.mark.asyncio
    async def test_worker_size_and_rate_limits_concurrency_and_freq(self):
        size = 3
        rate = 2
        num_tasks = 10
        task_duration = 2

        async def slow_task():
            await asyncio.sleep(task_duration)

        start_time = time.time()
        async with worker_pool(size, rate) as pool:
            results = []
            for _ in range(num_tasks):
                results.append(pool.run(slow_task))
            await asyncio.gather(*results)
        end_time = time.time()

        total_time = end_time - start_time
        expected_time = 8  # worked out manually for size 3, rate 2, 10 tasks, 2s duration
        assert total_time >= expected_time, f"Tasks completed faster than expected, {total_time} < {expected_time}"
        assert total_time <= expected_time * 1.05, f"Tasks took too long to complete, {total_time} > {expected_time}"

    @pytest.mark.asyncio
    async def test_worker_pool_does_not_accept_new_tasks_after_shutdown(self):
        async def simple_task():
            return 42

        async with worker_pool(size=1) as pool:
            result = await pool.run(simple_task)
            assert result == 42

        with pytest.raises(RuntimeError):
            await pool.run(simple_task)

    @pytest.mark.asyncio
    async def test_worker_pool_completes_all_tasks_before_shutdown(self):
        workers = WorkerPool(rate = 2)

        tasks_exectuded = 0
        async def slow_task():
            nonlocal tasks_exectuded
            await asyncio.sleep(1)
            tasks_exectuded += 1

        for _ in range(5):
            workers.run(slow_task)

        await workers.shutdown()

        assert tasks_exectuded == 5

    @pytest.mark.asyncio
    async def test_worker_pool_cancels_pending_tasks_on_kill(self):
        workers = WorkerPool(rate = 2)

        tasks_exectuded = 0
        async def slow_task():
            nonlocal tasks_exectuded
            await asyncio.sleep(1)
            tasks_exectuded += 1

        for _ in range(5):
            workers.run(slow_task)

        await workers.kill()

        assert tasks_exectuded < 5
