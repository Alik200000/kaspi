import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from app.workers.tasks import run_reprice_and_kaspi_sync_task, run_poll_kaspi_orders_task

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Asynchronous periodic task runner.
    Monitors execution state, history, and prevents overlapping task executions.
    """

    def __init__(self):
        self.is_running: bool = False
        self._bg_task: Optional[asyncio.Task] = None
        
        self.task_state: Dict[str, Dict[str, Any]] = {
            "reprice_and_kaspi_sync": {
                "interval_seconds": 300, # Every 5 minutes
                "last_run": None,
                "status": "IDLE",
                "last_result": None,
                "run_count": 0
            },
            "poll_kaspi_orders": {
                "interval_seconds": 120, # Every 2 minutes
                "last_run": None,
                "status": "IDLE",
                "last_result": None,
                "run_count": 0
            }
        }

    async def execute_task(self, task_name: str) -> Dict[str, Any]:
        """Runs a specific task on-demand and updates its state."""
        if task_name not in self.task_state:
            raise ValueError(f"Unknown task: {task_name}")

        state = self.task_state[task_name]
        if state["status"] == "RUNNING":
            return {"status": "skipped", "message": "Task is already executing"}

        state["status"] = "RUNNING"
        try:
            if task_name == "reprice_and_kaspi_sync":
                res = await run_reprice_and_kaspi_sync_task()
            elif task_name == "poll_kaspi_orders":
                res = await run_poll_kaspi_orders_task()
            else:
                res = {"status": "error", "message": "Unknown task handler"}

            state["status"] = "SUCCESS"
            state["last_result"] = res
            state["last_run"] = datetime.utcnow().isoformat()
            state["run_count"] += 1
            return res
        except Exception as e:
            logger.error(f"[SCHEDULER] Task {task_name} failed: {str(e)}", exc_info=True)
            state["status"] = "ERROR"
            state["last_result"] = {"error": str(e)}
            state["last_run"] = datetime.utcnow().isoformat()
            return {"status": "error", "message": str(e)}

    async def _scheduler_loop(self):
        """Main periodic polling loop."""
        logger.info("[SCHEDULER] Background worker loop started.")
        while self.is_running:
            now = datetime.utcnow()
            for task_name, state in self.task_state.items():
                interval = state["interval_seconds"]
                last_run_str = state["last_run"]
                
                should_run = False
                if not last_run_str:
                    should_run = True
                else:
                    last_run_dt = datetime.fromisoformat(last_run_str)
                    if (now - last_run_dt).total_seconds() >= interval:
                        should_run = True

                if should_run and state["status"] != "RUNNING":
                    asyncio.create_task(self.execute_task(task_name))

            await asyncio.sleep(10) # Tick every 10 seconds

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._bg_task = asyncio.create_task(self._scheduler_loop())
            logger.info("[SCHEDULER] Started scheduler background service.")

    def stop(self):
        self.is_running = False
        if self._bg_task:
            self._bg_task.cancel()
            logger.info("[SCHEDULER] Stopped scheduler service.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "scheduler_running": self.is_running,
            "tasks": self.task_state
        }


# Global singleton instance
scheduler = TaskScheduler()
