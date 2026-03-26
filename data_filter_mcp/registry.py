from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Event, RLock, Thread
from typing import Callable
from uuid import uuid4

from .models import FilterCallable, RegisteredFilter


class FilterRegistryError(RuntimeError):
    """Base registry error."""


class FilterNotFoundError(FilterRegistryError):
    """Raised when a filter id does not exist."""


class FilterExpiredError(FilterRegistryError):
    """Raised when a filter has passed its TTL."""


class FilterRegistry:
    def __init__(
        self,
        filter_ttl_seconds: int,
        cleanup_interval_seconds: float = 60.0,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if filter_ttl_seconds <= 0:
            raise ValueError("filter_ttl_seconds must be greater than zero")
        if cleanup_interval_seconds <= 0:
            raise ValueError("cleanup_interval_seconds must be greater than zero")

        self._filter_ttl_seconds = filter_ttl_seconds
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._filters: dict[str, RegisteredFilter] = {}
        self._lock = RLock()
        self._stop_event = Event()
        self._cleanup_thread: Thread | None = None

    @property
    def filter_ttl_seconds(self) -> int:
        return self._filter_ttl_seconds

    def register(
        self,
        source_code: str,
        function: FilterCallable,
        policy_version: str,
    ) -> RegisteredFilter:
        now = self._now_provider()
        filter_id = str(uuid4())
        entry = RegisteredFilter(
            filter_id=filter_id,
            function=function,
            source_code=source_code,
            created_at=now,
            expires_at=now + timedelta(seconds=self._filter_ttl_seconds),
            policy_version=policy_version,
        )
        with self._lock:
            self._filters[filter_id] = entry
        return entry

    def get(self, filter_id: str) -> RegisteredFilter:
        now = self._now_provider()
        with self._lock:
            entry = self._filters.get(filter_id)
            if entry is None:
                raise FilterNotFoundError(f"Unknown filter_id: {filter_id}")
            if entry.is_expired(now):
                del self._filters[filter_id]
                raise FilterExpiredError(f"Filter has expired: {filter_id}")
            return entry

    def cleanup_expired(self) -> int:
        now = self._now_provider()
        with self._lock:
            expired_ids = [
                filter_id
                for filter_id, entry in self._filters.items()
                if entry.is_expired(now)
            ]
            for filter_id in expired_ids:
                del self._filters[filter_id]
            return len(expired_ids)

    def start_cleanup_thread(self) -> None:
        with self._lock:
            if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
                return
            self._stop_event.clear()
            self._cleanup_thread = Thread(
                target=self._cleanup_loop,
                name="filter-registry-cleanup",
                daemon=True,
            )
            self._cleanup_thread.start()

    def stop_cleanup_thread(self) -> None:
        self._stop_event.set()
        thread = self._cleanup_thread
        if thread is not None:
            thread.join(timeout=self._cleanup_interval_seconds + 1.0)
        self._cleanup_thread = None

    def __len__(self) -> int:
        with self._lock:
            return len(self._filters)

    def _cleanup_loop(self) -> None:
        while not self._stop_event.wait(self._cleanup_interval_seconds):
            self.cleanup_expired()
