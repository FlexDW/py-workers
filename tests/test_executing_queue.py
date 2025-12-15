import asyncio
import pytest
from werkpool import WorkerPool


class TestExecutingQueue:
    """Tests specifically for the _executing list tracking"""

    @pytest.mark.asyncio
    async def test_executing_list_tracks_active_tasks(self):
        """Verify tasks move from queue to executing list"""
        workers = WorkerPool(size=2)
        started = asyncio.Event()
        can_finish = asyncio.Event()

        async def blocking_task():
            started.set()
            await can_finish.wait()

        # Start 3 tasks with size limit of 2
        f1 = workers.run(blocking_task)
        f2 = workers.run(blocking_task)
        f3 = workers.run(blocking_task)

        # Wait for first 2 to start
        await started.wait()
        await asyncio.sleep(0.1)

        # Should have 2 executing, 1 queued
        assert len(workers._executing) == 2
        assert len(workers._queue) == 1

        # Let them finish
        can_finish.set()
        await asyncio.gather(f1, f2, f3)

        # Should be clean
        assert len(workers._executing) == 0
        assert len(workers._queue) == 0

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_executing_and_queued(self):
        """Verify shutdown waits for both executing and queued tasks"""
        workers = WorkerPool(size=2, rate=2)
        execution_order = []

        async def tracked_task(task_id):
            execution_order.append(f"start_{task_id}")
            await asyncio.sleep(0.5)
            execution_order.append(f"end_{task_id}")

        # Create 5 tasks (2 executing, 3 queued due to size/rate limits)
        for i in range(5):
            workers.run(lambda i=i: tracked_task(i))

        await asyncio.sleep(0.1)  # Let some start

        # Should have tasks in both states
        assert len(workers._executing) > 0 or len(workers._queue) > 0

        # Shutdown should wait for all
        await workers.shutdown()

        # All tasks should complete
        assert len([x for x in execution_order if x.startswith("end_")]) == 5
        assert len(workers._executing) == 0
        assert len(workers._queue) == 0

    @pytest.mark.asyncio
    async def test_kill_cancels_both_executing_and_queued(self):
        """Verify kill cancels tasks in both states"""
        workers = WorkerPool(size=2)
        started_count = 0
        completed_count = 0

        async def slow_task():
            nonlocal started_count, completed_count
            started_count += 1
            await asyncio.sleep(2)
            completed_count += 1

        # Create 5 tasks
        futures = [workers.run(slow_task) for _ in range(5)]

        await asyncio.sleep(0.1)  # Let some start

        initial_executing = len(workers._executing)
        initial_queued = len(workers._queue)

        # Kill should cancel everything
        await workers.kill()

        # Queue should be empty (queued tasks cancelled)
        assert len(workers._queue) == 0
        
        # Some tasks started but not all completed
        assert started_count > 0
        assert completed_count < 5

        # Queued tasks should have CancelledError
        cancelled_count = 0
        for f in futures:
            if f.done():
                try:
                    f.result()
                except asyncio.CancelledError:
                    cancelled_count += 1

        assert cancelled_count >= initial_queued

    @pytest.mark.asyncio
    async def test_executing_list_cleanup_on_task_failure(self):
        """Verify _executing is cleaned up even when tasks fail"""
        workers = WorkerPool(size=5)

        async def failing_task():
            await asyncio.sleep(0.1)
            raise ValueError("Task failed")

        # Run multiple failing tasks
        futures = [workers.run(failing_task) for _ in range(3)]

        # Wait for all to complete (with exceptions)
        results = await asyncio.gather(*futures, return_exceptions=True)

        # All should fail
        assert all(isinstance(r, ValueError) for r in results)

        # Executing list should be clean
        assert len(workers._executing) == 0

    @pytest.mark.asyncio
    async def test_executing_list_with_retries(self):
        """Verify _executing tracks correctly during retries"""
        workers = WorkerPool(size=2)
        attempts = 0

        async def retry_task():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise TimeoutError("Retry me")
            return "success"

        future = workers.run(retry_task, retries=5, retryable_exceptions=[TimeoutError])

        # Should stay in executing during retries
        await asyncio.sleep(0.1)
        assert len(workers._executing) == 1

        result = await future
        assert result == "success"
        assert len(workers._executing) == 0

    @pytest.mark.asyncio
    async def test_no_new_tasks_after_shutdown_started(self):
        """Verify can't add tasks once shutdown begins"""
        workers = WorkerPool(size=2)

        async def quick_task():
            await asyncio.sleep(0.1)

        workers.run(quick_task)
        
        # Start shutdown (don't await yet)
        shutdown_task = asyncio.create_task(workers.shutdown())
        await asyncio.sleep(0.05)  # Let shutdown start

        # Should reject new tasks
        with pytest.raises(RuntimeError):
            workers.run(quick_task)

        await shutdown_task
