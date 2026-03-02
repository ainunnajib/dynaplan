import inspect
import json
import os
import socket
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from app.core.config import settings

try:
    from redis import asyncio as redis_asyncio
except Exception:  # pragma: no cover - import fallback for constrained envs
    redis_asyncio = None


_DEFAULT_ASSIGNMENT_TTL_SECONDS = 900
_DEFAULT_CACHE_TTL_SECONDS = 300
_MAX_EVENTS_PER_CHANNEL = 200

_KUBERNETES_MANIFEST_DIR = (
    Path(__file__).resolve().parent.parent.parent / "deploy" / "kubernetes"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> datetime:
    if value is None:
        return _utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except Exception:
        return _utcnow()


class HorizontalScalingRuntime:
    """
    Shared-state runtime for horizontally scaled API nodes.

    - Prefers Redis for cross-node state, pub/sub, and cache.
    - Falls back to in-memory mode when Redis is unavailable.
    """

    def __init__(self) -> None:
        configured_node_id = os.getenv("DYNAPLAN_NODE_ID", "").strip()
        self._node_id = configured_node_id or socket.gethostname()

        self._redis_url = settings.redis_url.strip()
        self._redis_client = None
        self._redis_active = False
        self._redis_error = None

        self._model_assignments: Dict[str, Dict[str, Any]] = {}
        self._cache_entries: Dict[str, Dict[str, Any]] = {}
        self._events_by_channel: Dict[str, Deque[Dict[str, Any]]] = {}

    @property
    def node_id(self) -> str:
        return self._node_id

    @staticmethod
    def _assignment_key(model_id: uuid.UUID) -> str:
        return "dynaplan:scaling:model-assignment:%s" % str(model_id)

    @staticmethod
    def _cache_key(namespace: str, cache_key: str) -> str:
        return "dynaplan:scaling:cache:%s:%s" % (namespace, cache_key)

    @staticmethod
    def _event_list_key(channel: str) -> str:
        return "dynaplan:scaling:events:%s" % channel

    @staticmethod
    def _event_pubsub_key(channel: str) -> str:
        return "dynaplan:scaling:pubsub:%s" % channel

    async def _get_redis_client(self):
        if not self._redis_url:
            return None
        if redis_asyncio is None:
            if self._redis_error is None:
                self._redis_error = "redis package unavailable"
            return None

        if self._redis_client is None:
            self._redis_client = redis_asyncio.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
        return self._redis_client

    async def _deactivate_redis(self, reason: str) -> None:
        self._redis_active = False
        self._redis_error = reason
        await self.close()

    async def _record_redis_success(self) -> None:
        self._redis_active = True
        self._redis_error = None

    def _prune_expired_assignments(self) -> None:
        now = _utcnow()
        expired_keys = []
        for key, value in self._model_assignments.items():
            expires_at = value["expires_at"]
            if expires_at <= now:
                expired_keys.append(key)
        for key in expired_keys:
            del self._model_assignments[key]

    def _prune_expired_cache_entries(self) -> None:
        now = _utcnow()
        expired_keys = []
        for key, value in self._cache_entries.items():
            expires_at = value["expires_at"]
            if expires_at <= now:
                expired_keys.append(key)
        for key in expired_keys:
            del self._cache_entries[key]

    @staticmethod
    def _sanitize_ttl(ttl_seconds: int, default_ttl: int) -> int:
        if ttl_seconds <= 0:
            return default_ttl
        return ttl_seconds

    @staticmethod
    def _build_assignment_payload(
        model_id: uuid.UUID,
        node_id: str,
        assigned_at: datetime,
        expires_at: datetime,
        backend: str,
    ) -> Dict[str, Any]:
        return {
            "model_id": str(model_id),
            "node_id": node_id,
            "assigned_at": _to_iso(assigned_at),
            "expires_at": _to_iso(expires_at),
            "backend": backend,
        }

    async def get_status(self) -> Dict[str, Any]:
        redis_client = await self._get_redis_client()
        if redis_client is not None:
            try:
                await redis_client.ping()
                await self._record_redis_success()
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        self._prune_expired_assignments()
        self._prune_expired_cache_entries()

        return {
            "node_id": self._node_id,
            "api_mode": "stateless",
            "load_balancer_strategy": "stateless_api_with_sticky_model_assignment",
            "state_backend": "redis" if self._redis_active else "memory",
            "redis_configured": bool(self._redis_url),
            "redis_active": self._redis_active,
            "redis_error": self._redis_error,
            "model_assignments_tracked": len(self._model_assignments),
            "cache_entries_tracked": len(self._cache_entries),
            "event_channels_tracked": len(self._events_by_channel),
        }

    async def assign_model(
        self,
        model_id: uuid.UUID,
        ttl_seconds: int = _DEFAULT_ASSIGNMENT_TTL_SECONDS,
        node_id: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        target_node_id = (node_id or self._node_id).strip() or self._node_id
        ttl = self._sanitize_ttl(ttl_seconds, _DEFAULT_ASSIGNMENT_TTL_SECONDS)
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl)

        payload = {
            "node_id": target_node_id,
            "assigned_at": _to_iso(now),
        }

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            key = self._assignment_key(model_id)
            encoded_payload = json.dumps(payload)
            try:
                if force:
                    await redis_client.set(key, encoded_payload, ex=ttl)
                    await self._record_redis_success()
                    return self._build_assignment_payload(
                        model_id=model_id,
                        node_id=target_node_id,
                        assigned_at=now,
                        expires_at=expires_at,
                        backend="redis",
                    )

                set_result = await redis_client.set(
                    key,
                    encoded_payload,
                    ex=ttl,
                    nx=True,
                )
                await self._record_redis_success()
                if set_result:
                    return self._build_assignment_payload(
                        model_id=model_id,
                        node_id=target_node_id,
                        assigned_at=now,
                        expires_at=expires_at,
                        backend="redis",
                    )

                existing_raw = await redis_client.get(key)
                existing_ttl = await redis_client.ttl(key)
                if existing_raw is not None:
                    parsed = json.loads(existing_raw)
                    existing_assigned_at = _parse_iso(parsed.get("assigned_at"))
                    ttl_remaining = (
                        int(existing_ttl)
                        if isinstance(existing_ttl, int) and existing_ttl > 0
                        else _DEFAULT_ASSIGNMENT_TTL_SECONDS
                    )
                    existing_expires_at = existing_assigned_at + timedelta(
                        seconds=ttl_remaining
                    )
                    return self._build_assignment_payload(
                        model_id=model_id,
                        node_id=str(parsed.get("node_id") or self._node_id),
                        assigned_at=existing_assigned_at,
                        expires_at=existing_expires_at,
                        backend="redis",
                    )
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        self._prune_expired_assignments()
        key = str(model_id)
        existing = self._model_assignments.get(key)
        if existing is not None and not force:
            return self._build_assignment_payload(
                model_id=model_id,
                node_id=existing["node_id"],
                assigned_at=existing["assigned_at"],
                expires_at=existing["expires_at"],
                backend="memory",
            )

        self._model_assignments[key] = {
            "node_id": target_node_id,
            "assigned_at": now,
            "expires_at": expires_at,
        }
        return self._build_assignment_payload(
            model_id=model_id,
            node_id=target_node_id,
            assigned_at=now,
            expires_at=expires_at,
            backend="memory",
        )

    async def get_model_assignment(
        self,
        model_id: uuid.UUID,
        auto_assign: bool = True,
        ttl_seconds: int = _DEFAULT_ASSIGNMENT_TTL_SECONDS,
    ) -> Optional[Dict[str, Any]]:
        redis_client = await self._get_redis_client()
        if redis_client is not None:
            key = self._assignment_key(model_id)
            try:
                raw_payload = await redis_client.get(key)
                await self._record_redis_success()
                if raw_payload is not None:
                    parsed = json.loads(raw_payload)
                    assigned_at = _parse_iso(parsed.get("assigned_at"))
                    ttl_remaining = await redis_client.ttl(key)
                    ttl_seconds_remaining = (
                        int(ttl_remaining)
                        if isinstance(ttl_remaining, int) and ttl_remaining > 0
                        else _DEFAULT_ASSIGNMENT_TTL_SECONDS
                    )
                    expires_at = assigned_at + timedelta(seconds=ttl_seconds_remaining)
                    return self._build_assignment_payload(
                        model_id=model_id,
                        node_id=str(parsed.get("node_id") or self._node_id),
                        assigned_at=assigned_at,
                        expires_at=expires_at,
                        backend="redis",
                    )
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        self._prune_expired_assignments()
        existing = self._model_assignments.get(str(model_id))
        if existing is not None:
            return self._build_assignment_payload(
                model_id=model_id,
                node_id=existing["node_id"],
                assigned_at=existing["assigned_at"],
                expires_at=existing["expires_at"],
                backend="memory",
            )

        if auto_assign:
            return await self.assign_model(
                model_id=model_id,
                ttl_seconds=ttl_seconds,
                force=False,
            )
        return None

    async def set_cache_entry(
        self,
        namespace: str,
        cache_key: str,
        value: Any,
        ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> Dict[str, Any]:
        ttl = self._sanitize_ttl(ttl_seconds, _DEFAULT_CACHE_TTL_SECONDS)
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl)
        payload = {
            "namespace": namespace,
            "key": cache_key,
            "value": value,
            "updated_at": _to_iso(now),
            "expires_at": _to_iso(expires_at),
        }

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            key = self._cache_key(namespace, cache_key)
            try:
                await redis_client.set(key, json.dumps(payload), ex=ttl)
                await self._record_redis_success()
                payload["backend"] = "redis"
                return payload
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        self._prune_expired_cache_entries()
        self._cache_entries[self._cache_key(namespace, cache_key)] = {
            "namespace": namespace,
            "key": cache_key,
            "value": value,
            "updated_at": now,
            "expires_at": expires_at,
        }
        payload["backend"] = "memory"
        return payload

    async def get_cache_entry(
        self,
        namespace: str,
        cache_key: str,
    ) -> Optional[Dict[str, Any]]:
        redis_client = await self._get_redis_client()
        if redis_client is not None:
            key = self._cache_key(namespace, cache_key)
            try:
                raw_payload = await redis_client.get(key)
                await self._record_redis_success()
                if raw_payload is not None:
                    parsed = json.loads(raw_payload)
                    parsed["backend"] = "redis"
                    return parsed
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        self._prune_expired_cache_entries()
        existing = self._cache_entries.get(self._cache_key(namespace, cache_key))
        if existing is None:
            return None
        return {
            "namespace": existing["namespace"],
            "key": existing["key"],
            "value": existing["value"],
            "updated_at": _to_iso(existing["updated_at"]),
            "expires_at": _to_iso(existing["expires_at"]),
            "backend": "memory",
        }

    async def publish_event(
        self,
        channel: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "channel": channel,
            "event_type": event_type,
            "payload": payload,
            "published_at": _to_iso(_utcnow()),
            "node_id": self._node_id,
            "backend": "memory",
        }

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            event_list_key = self._event_list_key(channel)
            event_pubsub_key = self._event_pubsub_key(channel)
            redis_event = dict(event)
            redis_event["backend"] = "redis"
            encoded = json.dumps(redis_event)
            try:
                await redis_client.lpush(event_list_key, encoded)
                await redis_client.ltrim(event_list_key, 0, _MAX_EVENTS_PER_CHANNEL - 1)
                await redis_client.publish(event_pubsub_key, encoded)
                await self._record_redis_success()
                event = redis_event
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        local_events = self._events_by_channel.setdefault(
            channel, deque(maxlen=_MAX_EVENTS_PER_CHANNEL)
        )
        local_events.appendleft(event)
        return event

    async def list_recent_events(
        self,
        channel: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            limit = 1
        if limit > 100:
            limit = 100

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            event_list_key = self._event_list_key(channel)
            try:
                raw_items = await redis_client.lrange(event_list_key, 0, limit - 1)
                await self._record_redis_success()
                parsed_items = []
                for item in raw_items:
                    parsed_items.append(json.loads(item))
                return parsed_items
            except Exception as exc:  # noqa: BLE001
                await self._deactivate_redis(str(exc))

        channel_events = self._events_by_channel.get(channel)
        if channel_events is None:
            return []
        return list(channel_events)[:limit]

    async def close(self) -> None:
        if self._redis_client is None:
            return

        close_method = getattr(self._redis_client, "aclose", None)
        if close_method is None:
            close_method = getattr(self._redis_client, "close", None)
        if close_method is not None:
            try:
                result = close_method()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass

        self._redis_client = None

    def reset_runtime_state(self) -> None:
        self._redis_active = False
        self._redis_error = None
        self._model_assignments.clear()
        self._cache_entries.clear()
        self._events_by_channel.clear()


def list_kubernetes_manifests() -> List[Dict[str, str]]:
    if not _KUBERNETES_MANIFEST_DIR.exists():
        return []

    manifests: List[Dict[str, str]] = []
    for path in sorted(_KUBERNETES_MANIFEST_DIR.glob("*.yaml")):
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        manifests.append({"name": path.name, "content": content})
    return manifests


horizontal_scaling_runtime = HorizontalScalingRuntime()


def reset_horizontal_scaling_runtime_state() -> None:
    horizontal_scaling_runtime.reset_runtime_state()


async def shutdown_horizontal_scaling_runtime() -> None:
    await horizontal_scaling_runtime.close()
