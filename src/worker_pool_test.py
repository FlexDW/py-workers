from unittest.mock import Mock
import asyncio
import time
import pytest
from worker_pool import worker_pool, Task, DelayedTask

class TestDelayedTask:
    @pytest.mark.asyncio
    async def test_successful_task_execution(self):
        # This test ensures that a simple task completes successfully without retries.
        async def simple_task():
            return "Success"

        task = Task(fn=simple_task)
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        result = await delayed_task.result()
        assert result == "Success"

    @pytest.mark.asyncio
    async def test_successful_task_execution_with_callback(self):
        # This test ensures that a simple task completes successfully and the callback is called.
        async def simple_task():
            return "Success"

        callback = Mock()
        task = Task(fn=simple_task)
        delayed_task = DelayedTask(task)
        await delayed_task.execute(callback)
        await delayed_task.result()
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_with_non_retryable_exception(self):
        # Tests that an exception is properly handled and re-raised if it's not retryable.
        async def faulty_task():
            raise ValueError("An error occurred")

        task = Task(fn=faulty_task, retryable_exceptions=(KeyError,))
        delayed_task = DelayedTask(task)
        with pytest.raises(ValueError):
            await delayed_task.execute()
            await delayed_task.result()

    @pytest.mark.asyncio
    async def test_task_with_multiple_retryable_exception_types(self):
        # This test ensures that a task is retried when it raises one of several retryable exceptions.
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
        result = await delayed_task.result()
        assert result == "Recovered"


    @pytest.mark.asyncio
    async def test_task_with_retryable_exception(self):
        # Ensure that retries are attempted for retryable exceptions and succeed on retry.
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
        result = await delayed_task.result()
        assert result == "Recovered"

    @pytest.mark.asyncio
    async def test_task_with_multiple_retryable_exception_types(self):
        # This test ensures that a task is retried when it raises one of several retryable exceptions.
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
        result = await delayed_task.result()
        assert result == "Recovered"

    @pytest.mark.asyncio
    async def test_task_with_retries_backoff_called(self):
        # This test ensures that the backoff function is called when a task is retried.
        attempts = 0

        async def occasionally_faulty_task():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise TimeoutError("Timeout")
            return "Recovered"

        def backoff(attempts):
            assert attempts == 1
            return 1

        task = Task(fn=occasionally_faulty_task, retries=3, retryable_exceptions=(TimeoutError,), backoff=backoff)
        delayed_task = DelayedTask(task)
        await delayed_task.execute()
        await delayed_task.result()

    @pytest.mark.asyncio
    async def test_task_with_too_many_retries(self):
        # This test ensures that a task that fails too many times is not retried indefinitely.
        async def faulty_task():
            raise TimeoutError("Timeout")

        task = Task(fn=faulty_task, retries=3, retryable_exceptions=(TimeoutError,))
        delayed_task = DelayedTask(task)
        with pytest.raises(TimeoutError):
            await delayed_task.execute()
            await delayed_task.result()

class TestWorkerPool:
    @pytest.mark.asyncio
    async def test_worker_pool_run(self):
        # Test running a single task through a WorkerPool
        async def simple_task():
            return 42

        async with worker_pool(size=1) as pool:
            task = Task(fn=simple_task)
            result = await pool.run(task)
            assert result == 42

    @pytest.mark.asyncio
    async def test_worker_pool_limits_concurrent_workers(self):
        size = 5
        num_tasks = 10
        task_duration = 1

        async def slow_task():
            print("Running slow task")
            await asyncio.sleep(task_duration)

        start_time = time.time()
        async with worker_pool(size) as pool:  # No rate limit
            print("initing")
            results = []
            for _ in range(num_tasks):
                print("running")
                results.append(pool.run(Task(slow_task)))
            print("done")
            await asyncio.gather(*results)
            print("gathered")
        end_time = time.time()

        # Assert
        total_time = end_time - start_time
        expected_time = (num_tasks / size) * task_duration  # tasks per worker
        assert total_time >= expected_time, "Tasks completed faster than expected"
        assert total_time <= expected_time * 2, "Tasks took too long to complete"


    # @pytest.mark.asyncio
    # async def test_worker_pool_respects_limits(self):
    #     size = 5
    #     rate = 3
    #     num_tasks = 10
    #     task_duration = 2

    #     async def slow_task():
    #         await asyncio.sleep(task_duration)

    #     start_time = time.time()
    #     async with worker_pool(size, rate) as pool:
    #         for _ in range(num_tasks):
    #             pool.run(slow_task)
    #     end_time = time.time()

    #     total_time = end_time - start_time
    #     expected_time = num_tasks / rate  # tasks per second
    #     assert total_time >= expected_time, "Tasks completed faster than expected rate"
    #     assert total_time <= expected_time * 2, "Tasks took too long to complete"

    @pytest.mark.asyncio
    async def test_worker_pool_accepts_new_tasks(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_executes_tasks(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_handles_task_exceptions(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_does_not_accept_new_tasks_after_shutdown(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_completes_all_tasks_before_shutdown(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_cancels_pending_tasks_on_kill(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_respects_max_workers_limit(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_recovers_from_worker_failure(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_handles_multiple_concurrent_tasks(self):
        pass

    @pytest.mark.asyncio
    async def test_worker_pool_handles_task_cancellation(self):
        pass
