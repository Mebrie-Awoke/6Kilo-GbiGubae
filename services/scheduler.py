"""Legacy import shim.

The in-memory scheduler has been retired. Scheduled broadcasts now run from
services.durable_broadcasts and are triggered by the external GitHub Actions
workflow, so Render does not need a continuously running scheduler loop.
"""

from services.durable_broadcasts import (
    materialize_due_schedules,
    process_pending_deliveries,
    run_scheduled_broadcasts,
)

__all__ = [
    "materialize_due_schedules",
    "process_pending_deliveries",
    "run_scheduled_broadcasts",
]
