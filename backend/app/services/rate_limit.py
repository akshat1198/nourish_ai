"""Per-user daily quota for the endpoints that spend money.

Unlike `services/cache.py`, this FAILS CLOSED. The cache degrades to a miss when
Redis is unavailable because the cost of being wrong there is a slower request;
here the cost of being wrong is unmetered spend against the Anthropic key, and
Redis has already been unreachable for weeks at a stretch on this deployment. An
endpoint that cannot count its own calls does not get to make them.

A calendar-day counter rather than a sliding window: what is being protected is a
daily spend ceiling, and a plain INCR with a TTL needs one round trip and no
reasoning about clock skew.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.cache import redis_client

logger = logging.getLogger(__name__)


class RateLimitUnavailable(RuntimeError):
    """Redis could not be reached, so the quota cannot be enforced."""


class RateLimitExceeded(RuntimeError):
    def __init__(self, bucket: str, limit: int, used: int):
        self.bucket = bucket
        self.limit = limit
        self.used = used
        super().__init__(f"{bucket}: {used}/{limit} calls used today")


def _key(bucket: str, user_key: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"rl:{bucket}:{user_key}:{day}"


def consume(bucket: str, user_key: str, limit: int) -> int:
    """Count one call against today's quota and return how many calls remain.

    Raises RateLimitExceeded once the limit is passed, RateLimitUnavailable if
    Redis cannot be reached. A limit of 0 or less disables the quota.
    """
    if limit <= 0:
        return -1  # unlimited

    key = _key(bucket, user_key)
    try:
        used = redis_client.incr(key)
        if used == 1:
            # Set the TTL only on the day's first call, so a burst cannot keep
            # pushing the expiry out and leave the counter immortal.
            redis_client.expire(key, 60 * 60 * 25)
    except Exception as e:
        logger.warning(
            "rate limit unavailable for %s (%s): %s", bucket, type(e).__name__, e
        )
        raise RateLimitUnavailable(str(e)) from e

    if used > limit:
        raise RateLimitExceeded(bucket=bucket, limit=limit, used=used)
    return limit - used
