from fastapi import APIRouter, HTTPException, Depends
from app.workers.scheduler import scheduler
from app.modules.auth.deps import require_roles

router = APIRouter(prefix="/tasks", tags=["Background Tasks & Automation"])


@router.get("/status")
async def get_tasks_status():
    """
    Returns real-time status of all periodic automation jobs:
    - reprice_and_kaspi_sync (auto recalculation of prices and Kaspi catalog sync)
    - poll_kaspi_orders (periodic polling of new marketplace orders)
    """
    return scheduler.get_status()


@router.post("/run/{task_name}")
async def trigger_task_manually(task_name: str):
    """
    Triggers an automated background job immediately on demand.
    Allowed tasks: 'reprice_and_kaspi_sync', 'poll_kaspi_orders'.
    """
    try:
        result = await scheduler.execute_task(task_name)
        return {
            "triggered_task": task_name,
            "execution_result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
