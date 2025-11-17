"""
Scheduler service for automated tasks.

Handles scheduled tasks such as:
- Hourly Google Drive Trash cleanup
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.services.google_drive_service import google_drive_service


class SchedulerService:
    """Service for managing scheduled background tasks."""

    def __init__(self):
        """Initialize the scheduler service."""
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._is_running = False
        logging.info("Scheduler service initialized")

    def start(self):
        """
        Start the scheduler and register all scheduled tasks.

        Called during FastAPI lifespan startup.
        """
        if self._is_running:
            logging.warning("Scheduler is already running")
            return

        try:
            # Create AsyncIO scheduler
            self.scheduler = AsyncIOScheduler(timezone="UTC")

            # Register scheduled tasks
            self._register_trash_cleanup()

            # Start the scheduler
            self.scheduler.start()
            self._is_running = True

            logging.info("=" * 80)
            logging.info("🚀 SCHEDULER STARTED SUCCESSFULLY")
            logging.info("=" * 80)
            logging.info("Registered tasks:")
            for job in self.scheduler.get_jobs():
                logging.info(f"   - {job.id}: {job.next_run_time}")
            logging.info("=" * 80)

            print("\n🚀 Scheduler started successfully")
            print(f"   Active jobs: {len(self.scheduler.get_jobs())}")

        except Exception as e:
            logging.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """
        Stop the scheduler gracefully.

        Called during FastAPI lifespan shutdown.
        """
        if not self._is_running or not self.scheduler:
            logging.warning("Scheduler is not running")
            return

        try:
            logging.info("Stopping scheduler...")
            self.scheduler.shutdown(wait=True)
            self._is_running = False

            logging.info("=" * 80)
            logging.info("🛑 SCHEDULER STOPPED")
            logging.info("=" * 80)

            print("\n🛑 Scheduler stopped\n")

        except Exception as e:
            logging.error(f"Error stopping scheduler: {e}")
            raise

    def _register_trash_cleanup(self):
        """
        Register the hourly Google Drive trash cleanup task.

        Runs every hour at minute 0 (e.g., 10:00, 11:00, 12:00, etc.)
        """
        # Use CronTrigger to run at the top of every hour
        trigger = CronTrigger(minute=0, timezone="UTC")

        self.scheduler.add_job(
            func=self._trash_cleanup_job,
            trigger=trigger,
            id="trash_cleanup_hourly",
            name="Google Drive Trash Cleanup (Hourly)",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            coalesce=True,  # If multiple runs are missed, only run once
            misfire_grace_time=300  # Allow up to 5 minutes late execution
        )

        logging.info("✓ Registered: Google Drive Trash Cleanup (runs hourly at :00)")

    async def _trash_cleanup_job(self):
        """
        Execute the Google Drive trash cleanup task.

        This is the actual job function called by the scheduler.
        Wraps the google_drive_service.clean_trash_folder() method.
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            logging.info(f"\n{'=' * 80}")
            logging.info(f"⏰ SCHEDULED TASK TRIGGERED: Trash Cleanup at {timestamp}")
            logging.info(f"{'=' * 80}")

            # Call the trash cleanup function
            result = await google_drive_service.clean_trash_folder()

            # Log summary
            if result.get('trash_was_empty'):
                logging.info(f"✅ Scheduled trash cleanup completed: Trash was empty")
            else:
                logging.info(
                    f"✅ Scheduled trash cleanup completed: "
                    f"Deleted {result.get('files_deleted', 0)} files "
                    f"({result.get('total_size_mb', 0)} MB) "
                    f"in {result.get('duration_seconds', 0)}s"
                )

        except Exception as e:
            logging.error(f"❌ Scheduled trash cleanup failed: {e}")
            # Don't re-raise - we don't want to crash the scheduler


# Global scheduler instance
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Get or create the global scheduler service instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


# For convenient import
scheduler_service = get_scheduler_service()
