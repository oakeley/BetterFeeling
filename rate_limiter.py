import time
import logging
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter using token bucket algorithm with per-minute and per-hour limits"""

    def __init__(self, requests_per_minute, requests_per_hour):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_requests = deque()
        self.hour_requests = deque()
        self.lock = Lock()

    def _clean_old_requests(self, request_queue, time_window):
        """Remove requests older than the time window"""
        current_time = time.time()
        while request_queue and current_time - request_queue[0] > time_window:
            request_queue.popleft()

    def acquire(self, timeout=60):
        """Attempt to acquire permission to make a request, returns True if successful"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self.lock:
                current_time = time.time()

                self._clean_old_requests(self.minute_requests, 60)
                self._clean_old_requests(self.hour_requests, 3600)

                minute_count = len(self.minute_requests)
                hour_count = len(self.hour_requests)

                if minute_count < self.requests_per_minute and hour_count < self.requests_per_hour:
                    self.minute_requests.append(current_time)
                    self.hour_requests.append(current_time)
                    return True

            time.sleep(0.1)

        logger.warning("Rate limiter timeout after %d seconds", timeout)
        return False

class RateLimiterManager:
    """Manages rate limiters for different APIs"""

    def __init__(self, config):
        self.limiters = {}
        for api_name, limits in config.items():
            self.limiters[api_name] = RateLimiter(
                limits['requests_per_minute'],
                limits['requests_per_hour']
            )
        logger.info("Rate limiter manager initialized with %d APIs", len(self.limiters))

    def acquire(self, api_name, timeout=60):
        """Acquire rate limit token for a specific API"""
        if api_name not in self.limiters:
            logger.warning("No rate limiter configured for API: %s", api_name)
            return True

        return self.limiters[api_name].acquire(timeout)
