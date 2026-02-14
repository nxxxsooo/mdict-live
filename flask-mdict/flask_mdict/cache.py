"""Dual-backend cache: in-process LRU (default) or Valkey/Redis (optional).

Usage:
    Default (zero config):  in-memory LRU cache
    Optional Valkey:        set REDIS_URL env var (e.g. redis://valkey:6379/0)

The cache stores lookup results for dictionary queries. Dictionary content is
immutable at runtime (.mdx files don't change), so most entries never expire.
"""

import json
import logging
import os
import threading
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseCache(ABC):
    @abstractmethod
    def get(self, key):
        """Get a cached value. Returns None on miss."""

    @abstractmethod
    def set(self, key, value, ttl=None):
        """Set a cached value. ttl in seconds, None = no expiry."""

    @abstractmethod
    def delete_prefix(self, prefix):
        """Delete all keys matching a prefix."""

    @abstractmethod
    def clear(self):
        """Clear all cached data."""

    @abstractmethod
    def info(self):
        """Return cache backend info dict."""


class MemoryCache(BaseCache):
    """Thread-safe in-process LRU cache using cachetools."""

    def __init__(self, maxsize=4096):
        from cachetools import LRUCache

        self._cache = LRUCache(maxsize=maxsize)
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def get(self, key):
        with self._lock:
            return self._cache.get(key)

    def set(self, key, value, ttl=None):
        # MemoryCache ignores ttl — LRU eviction handles memory pressure
        with self._lock:
            self._cache[key] = value

    def delete_prefix(self, prefix):
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]

    def clear(self):
        with self._lock:
            self._cache.clear()

    def info(self):
        with self._lock:
            return {
                "backend": "memory",
                "maxsize": self._maxsize,
                "currsize": self._cache.currsize,
            }


class ValkeyCache(BaseCache):
    """Valkey/Redis cache backend."""

    def __init__(self, url):
        try:
            import valkey

            self._client = valkey.from_url(url, decode_responses=True)
        except ImportError:
            import redis

            self._client = redis.from_url(url, decode_responses=True)
        self._url = url

    def get(self, key):
        data = self._client.get(key)
        if data is not None:
            return json.loads(data)
        return None

    def set(self, key, value, ttl=None):
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if ttl:
            self._client.setex(key, ttl, data)
        else:
            self._client.set(key, data)

    def delete_prefix(self, prefix):
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=prefix + "*", count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def clear(self):
        self._client.flushdb()

    def info(self):
        info = self._client.info("memory")
        return {
            "backend": "valkey",
            "url": self._url,
            "used_memory_human": info.get("used_memory_human", "?"),
            "maxmemory_human": info.get("maxmemory_human", "?"),
        }


def init_cache():
    """Initialize cache backend based on environment.

    Priority: REDIS_URL env var → fallback to in-memory LRU.
    """
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            cache = ValkeyCache(redis_url)
            cache._client.ping()
            logger.info(" * Cache: Valkey (%s)" % redis_url)
            return cache
        except Exception as e:
            logger.warning(
                " * Valkey unavailable (%s), falling back to memory cache" % e
            )

    maxsize = int(os.environ.get("CACHE_SIZE", "4096"))
    cache = MemoryCache(maxsize=maxsize)
    logger.info(" * Cache: in-memory LRU (maxsize=%d)" % maxsize)
    return cache
