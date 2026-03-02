import base64
import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cell import CellValue
from app.models.model_encryption import ModelEncryptionKey
from app.models.module import LineItem, Module
from app.models.planning_model import PlanningModel

KMS_PROVIDER_LOCAL = "local"
KMS_PROVIDER_AWS = "aws_kms"
KMS_PROVIDER_VAULT = "vault"
SUPPORTED_KMS_PROVIDERS = {KMS_PROVIDER_LOCAL, KMS_PROVIDER_AWS, KMS_PROVIDER_VAULT}

_UNWRAPPED_KEY_CACHE: Dict[uuid.UUID, str] = {}


class ModelEncryptionError(ValueError):
    """Base error for model encryption operations."""


class ModelEncryptionValidationError(ModelEncryptionError):
    """Raised for invalid model encryption parameters."""


class ModelEncryptionProviderError(ModelEncryptionError):
    """Raised when a KMS provider operation fails."""


class ModelEncryptionNotEnabledError(ModelEncryptionError):
    """Raised when a model has no active encryption key."""


def _normalize_provider(kms_provider: Optional[str]) -> str:
    provider = (kms_provider or KMS_PROVIDER_LOCAL).strip().lower()
    if provider not in SUPPORTED_KMS_PROVIDERS:
        raise ModelEncryptionValidationError(
            "kms_provider must be one of: local, aws_kms, vault"
        )
    return provider


def _validate_provider_key_reference(
    kms_provider: str,
    kms_key_id: Optional[str],
) -> None:
    if kms_provider == KMS_PROVIDER_LOCAL:
        return
    if not kms_key_id:
        raise ModelEncryptionValidationError(
            "kms_key_id is required for external KMS providers"
        )


def _local_master_fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _aws_wrap_key(raw_data_key: bytes, kms_key_id: str) -> str:
    try:
        import boto3
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError(
            "AWS KMS provider requires boto3 to be installed"
        ) from exc

    try:
        client = boto3.client("kms")
        response = client.encrypt(
            KeyId=kms_key_id,
            Plaintext=raw_data_key,
        )
        ciphertext = response["CiphertextBlob"]
        if isinstance(ciphertext, memoryview):
            ciphertext = ciphertext.tobytes()
        return base64.b64encode(ciphertext).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError(
            "AWS KMS encrypt failed: %s" % exc
        ) from exc


def _aws_unwrap_key(wrapped_key: str) -> bytes:
    try:
        import boto3
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError(
            "AWS KMS provider requires boto3 to be installed"
        ) from exc

    try:
        client = boto3.client("kms")
        response = client.decrypt(
            CiphertextBlob=base64.b64decode(wrapped_key.encode("ascii")),
        )
        plaintext = response["Plaintext"]
        if isinstance(plaintext, memoryview):
            plaintext = plaintext.tobytes()
        return plaintext
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError(
            "AWS KMS decrypt failed: %s" % exc
        ) from exc


def _vault_encrypt(raw_data_key: bytes, kms_key_id: str) -> str:
    if not settings.vault_addr or not settings.vault_token:
        raise ModelEncryptionProviderError(
            "Vault KMS requires DYNAPLAN_VAULT_ADDR and DYNAPLAN_VAULT_TOKEN"
        )

    payload = {"plaintext": base64.b64encode(raw_data_key).decode("ascii")}
    url = (
        settings.vault_addr.rstrip("/")
        + "/v1/"
        + settings.vault_transit_mount.strip("/")
        + "/encrypt/"
        + kms_key_id
    )
    headers = {"X-Vault-Token": settings.vault_token}

    try:
        with httpx.Client(timeout=settings.vault_timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return str(data["data"]["ciphertext"])
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError(
            "Vault encrypt failed: %s" % exc
        ) from exc


def _vault_decrypt(wrapped_key: str, kms_key_id: str) -> bytes:
    if not settings.vault_addr or not settings.vault_token:
        raise ModelEncryptionProviderError(
            "Vault KMS requires DYNAPLAN_VAULT_ADDR and DYNAPLAN_VAULT_TOKEN"
        )

    payload = {"ciphertext": wrapped_key}
    url = (
        settings.vault_addr.rstrip("/")
        + "/v1/"
        + settings.vault_transit_mount.strip("/")
        + "/decrypt/"
        + kms_key_id
    )
    headers = {"X-Vault-Token": settings.vault_token}

    try:
        with httpx.Client(timeout=settings.vault_timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            plaintext = str(data["data"]["plaintext"])
            return base64.b64decode(plaintext.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError(
            "Vault decrypt failed: %s" % exc
        ) from exc


def _wrap_data_key(
    raw_data_key: str,
    kms_provider: str,
    kms_key_id: Optional[str],
) -> str:
    raw_bytes = raw_data_key.encode("ascii")
    if kms_provider == KMS_PROVIDER_LOCAL:
        return _local_master_fernet().encrypt(raw_bytes).decode("utf-8")
    if kms_provider == KMS_PROVIDER_AWS:
        return _aws_wrap_key(raw_bytes, str(kms_key_id))
    if kms_provider == KMS_PROVIDER_VAULT:
        return _vault_encrypt(raw_bytes, str(kms_key_id))
    raise ModelEncryptionValidationError("Unsupported kms_provider: %s" % kms_provider)


def _unwrap_data_key(model_key: ModelEncryptionKey) -> str:
    if model_key.kms_provider == KMS_PROVIDER_LOCAL:
        try:
            raw = _local_master_fernet().decrypt(model_key.wrapped_key.encode("utf-8"))
            return raw.decode("ascii")
        except InvalidToken as exc:
            raise ModelEncryptionProviderError(
                "Failed to decrypt local wrapped key"
            ) from exc

    if model_key.kms_provider == KMS_PROVIDER_AWS:
        return _aws_unwrap_key(model_key.wrapped_key).decode("ascii")

    if model_key.kms_provider == KMS_PROVIDER_VAULT:
        if not model_key.kms_key_id:
            raise ModelEncryptionProviderError("Vault key is missing kms_key_id")
        return _vault_decrypt(model_key.wrapped_key, model_key.kms_key_id).decode("ascii")

    raise ModelEncryptionValidationError(
        "Unsupported kms_provider: %s" % model_key.kms_provider
    )


async def _model_exists(db: AsyncSession, model_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(PlanningModel.id).where(PlanningModel.id == model_id)
    )
    return result.scalar_one_or_none() is not None


async def list_model_encryption_keys(
    db: AsyncSession, model_id: uuid.UUID
) -> List[ModelEncryptionKey]:
    result = await db.execute(
        select(ModelEncryptionKey)
        .where(ModelEncryptionKey.model_id == model_id)
        .order_by(ModelEncryptionKey.key_version.asc())
    )
    return list(result.scalars().all())


async def get_active_model_encryption_key(
    db: AsyncSession, model_id: uuid.UUID
) -> Optional[ModelEncryptionKey]:
    result = await db.execute(
        select(ModelEncryptionKey)
        .where(
            ModelEncryptionKey.model_id == model_id,
            ModelEncryptionKey.is_active == True,  # noqa: E712
        )
        .order_by(ModelEncryptionKey.key_version.desc())
    )
    return result.scalars().first()


async def get_model_encryption_status(
    db: AsyncSession, model_id: uuid.UUID
) -> Dict[str, Any]:
    keys = await list_model_encryption_keys(db, model_id)
    active_key = next((key for key in keys if key.is_active), None)
    return {
        "model_id": model_id,
        "encryption_enabled": active_key is not None,
        "active_key_version": active_key.key_version if active_key else None,
        "kms_provider": active_key.kms_provider if active_key else None,
        "kms_key_id": active_key.kms_key_id if active_key else None,
        "key_count": len(keys),
        "rotated_at": keys[-1].created_at if keys else None,
    }


async def _next_key_version(db: AsyncSession, model_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.max(ModelEncryptionKey.key_version)).where(
            ModelEncryptionKey.model_id == model_id
        )
    )
    max_version = result.scalar_one_or_none()
    return int(max_version or 0) + 1


def _infer_legacy_cell_type(cell: CellValue) -> str:
    if cell.value_boolean is not None:
        return "boolean"
    if cell.value_number is not None:
        return "number"
    if cell.value_text is not None:
        return "text"
    return "null"


def _legacy_cell_scalar(cell: CellValue) -> Any:
    if cell.value_boolean is not None:
        return cell.value_boolean
    if cell.value_number is not None:
        return cell.value_number
    if cell.value_text is not None:
        return cell.value_text
    return None


def _serialize_cell_payload(
    value_number: Optional[float],
    value_text: Optional[str],
    value_boolean: Optional[bool],
) -> str:
    if value_boolean is not None:
        payload = {"value_type": "boolean", "value": value_boolean}
    elif value_number is not None:
        payload = {"value_type": "number", "value": value_number}
    elif value_text is not None:
        payload = {"value_type": "text", "value": value_text}
    else:
        payload = {"value_type": "null", "value": None}
    return json.dumps(payload, separators=(",", ":"))


def _deserialize_cell_payload(payload: str) -> Tuple[Any, str]:
    parsed = json.loads(payload)
    value_type = str(parsed.get("value_type") or "null")
    value = parsed.get("value")

    if value_type == "boolean":
        if isinstance(value, bool):
            return value, value_type
        if isinstance(value, str):
            lowered = value.strip().lower()
            return lowered in {"true", "1", "yes"}, value_type
        return bool(value), value_type

    if value_type == "number":
        return (float(value) if value is not None else None), value_type

    if value_type == "text":
        return (str(value) if value is not None else None), value_type

    return None, "null"


async def _resolve_model_id_for_line_item(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(Module.model_id)
        .select_from(LineItem)
        .join(Module, Module.id == LineItem.module_id)
        .where(LineItem.id == line_item_id)
    )
    return result.scalar_one_or_none()


async def _get_key_by_id(
    db: AsyncSession,
    key_id: uuid.UUID,
    key_record_cache: Optional[Dict[uuid.UUID, ModelEncryptionKey]] = None,
) -> Optional[ModelEncryptionKey]:
    if key_record_cache is not None and key_id in key_record_cache:
        return key_record_cache[key_id]

    result = await db.execute(
        select(ModelEncryptionKey).where(ModelEncryptionKey.id == key_id)
    )
    key = result.scalar_one_or_none()
    if key_record_cache is not None and key is not None:
        key_record_cache[key_id] = key
    return key


async def _resolve_key_for_cell(
    db: AsyncSession,
    cell: CellValue,
    key_record_cache: Optional[Dict[uuid.UUID, ModelEncryptionKey]] = None,
) -> Optional[ModelEncryptionKey]:
    if cell.encryption_key_id is not None:
        by_id = await _get_key_by_id(db, cell.encryption_key_id, key_record_cache)
        if by_id is not None:
            return by_id

    model_id = await _resolve_model_id_for_line_item(db, cell.line_item_id)
    if model_id is None:
        return None

    active_key = await get_active_model_encryption_key(db, model_id)
    if (
        key_record_cache is not None
        and active_key is not None
        and active_key.id is not None
    ):
        key_record_cache[active_key.id] = active_key
    return active_key


def _get_unwrapped_key_from_cache(
    key_record: ModelEncryptionKey,
    data_key_cache: Optional[Dict[uuid.UUID, str]] = None,
) -> str:
    if data_key_cache is not None and key_record.id in data_key_cache:
        return data_key_cache[key_record.id]
    if key_record.id in _UNWRAPPED_KEY_CACHE:
        unwrapped = _UNWRAPPED_KEY_CACHE[key_record.id]
        if data_key_cache is not None:
            data_key_cache[key_record.id] = unwrapped
        return unwrapped

    unwrapped = _unwrap_data_key(key_record)
    _UNWRAPPED_KEY_CACHE[key_record.id] = unwrapped
    if data_key_cache is not None:
        data_key_cache[key_record.id] = unwrapped
    return unwrapped


def _fernet_for_data_key(data_key: str) -> Fernet:
    try:
        return Fernet(data_key.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise ModelEncryptionProviderError("Invalid model data key") from exc


async def get_cell_scalar_value(
    db: AsyncSession,
    cell: CellValue,
    key_record_cache: Optional[Dict[uuid.UUID, ModelEncryptionKey]] = None,
    data_key_cache: Optional[Dict[uuid.UUID, str]] = None,
) -> Tuple[Any, str]:
    if not cell.value_encrypted:
        return _legacy_cell_scalar(cell), _infer_legacy_cell_type(cell)

    model_key = await _resolve_key_for_cell(db, cell, key_record_cache=key_record_cache)
    if model_key is None:
        raise ModelEncryptionProviderError(
            "Encrypted cell has no resolvable model encryption key"
        )

    data_key = _get_unwrapped_key_from_cache(model_key, data_key_cache=data_key_cache)
    fernet = _fernet_for_data_key(data_key)
    try:
        plaintext = fernet.decrypt(cell.value_encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ModelEncryptionProviderError("Failed to decrypt cell payload") from exc
    return _deserialize_cell_payload(plaintext)


async def get_cell_value_components(
    db: AsyncSession,
    cell: CellValue,
    key_record_cache: Optional[Dict[uuid.UUID, ModelEncryptionKey]] = None,
    data_key_cache: Optional[Dict[uuid.UUID, str]] = None,
) -> Tuple[Optional[float], Optional[str], Optional[bool], str]:
    value, value_type = await get_cell_scalar_value(
        db,
        cell,
        key_record_cache=key_record_cache,
        data_key_cache=data_key_cache,
    )
    if value_type == "boolean":
        return None, None, value if isinstance(value, bool) else bool(value), value_type
    if value_type == "number":
        return (float(value) if value is not None else None), None, None, value_type
    if value_type == "text":
        return None, (str(value) if value is not None else None), None, value_type
    return None, None, None, "null"


async def encrypt_cell_components_with_key(
    db: AsyncSession,
    model_key: ModelEncryptionKey,
    value_number: Optional[float],
    value_text: Optional[str],
    value_boolean: Optional[bool],
    data_key_cache: Optional[Dict[uuid.UUID, str]] = None,
) -> str:
    del db
    payload = _serialize_cell_payload(
        value_number=value_number,
        value_text=value_text,
        value_boolean=value_boolean,
    )
    data_key = _get_unwrapped_key_from_cache(model_key, data_key_cache=data_key_cache)
    fernet = _fernet_for_data_key(data_key)
    return fernet.encrypt(payload.encode("utf-8")).decode("utf-8")


async def _reencrypt_model_cells(
    db: AsyncSession,
    model_id: uuid.UUID,
    target_key: ModelEncryptionKey,
) -> None:
    result = await db.execute(
        select(CellValue)
        .join(LineItem, LineItem.id == CellValue.line_item_id)
        .join(Module, Module.id == LineItem.module_id)
        .where(Module.model_id == model_id)
    )
    cells = list(result.scalars().all())
    if not cells:
        return

    key_record_cache: Dict[uuid.UUID, ModelEncryptionKey] = {}
    data_key_cache: Dict[uuid.UUID, str] = {}

    for cell in cells:
        value_number, value_text, value_boolean, _value_type = await get_cell_value_components(
            db,
            cell,
            key_record_cache=key_record_cache,
            data_key_cache=data_key_cache,
        )
        encrypted = await encrypt_cell_components_with_key(
            db,
            model_key=target_key,
            value_number=value_number,
            value_text=value_text,
            value_boolean=value_boolean,
            data_key_cache=data_key_cache,
        )
        cell.value_encrypted = encrypted
        cell.encryption_key_id = target_key.id
        cell.value_number = None
        cell.value_text = None
        cell.value_boolean = None


def clear_model_encryption_key_cache() -> None:
    _UNWRAPPED_KEY_CACHE.clear()


async def enable_model_encryption(
    db: AsyncSession,
    model_id: uuid.UUID,
    kms_provider: Optional[str] = None,
    kms_key_id: Optional[str] = None,
) -> ModelEncryptionKey:
    provider = _normalize_provider(kms_provider)
    _validate_provider_key_reference(provider, kms_key_id)

    if not await _model_exists(db, model_id):
        raise ModelEncryptionValidationError("Model not found")

    active_key = await get_active_model_encryption_key(db, model_id)
    if active_key is not None:
        raise ModelEncryptionValidationError("Model encryption is already enabled")

    key_version = await _next_key_version(db, model_id)
    raw_data_key = Fernet.generate_key().decode("ascii")
    wrapped_key = _wrap_data_key(
        raw_data_key=raw_data_key,
        kms_provider=provider,
        kms_key_id=kms_key_id,
    )

    key = ModelEncryptionKey(
        model_id=model_id,
        key_version=key_version,
        kms_provider=provider,
        kms_key_id=kms_key_id,
        wrapped_key=wrapped_key,
        is_active=True,
    )
    db.add(key)
    await db.flush()
    await _reencrypt_model_cells(db, model_id, key)
    await db.commit()
    await db.refresh(key)
    clear_model_encryption_key_cache()
    return key


async def rotate_model_encryption_key(
    db: AsyncSession,
    model_id: uuid.UUID,
    kms_provider: Optional[str] = None,
    kms_key_id: Optional[str] = None,
) -> ModelEncryptionKey:
    current_key = await get_active_model_encryption_key(db, model_id)
    if current_key is None:
        raise ModelEncryptionNotEnabledError("Model encryption is not enabled")

    provider = _normalize_provider(kms_provider or current_key.kms_provider)
    target_kms_key_id = kms_key_id
    if target_kms_key_id is None:
        target_kms_key_id = current_key.kms_key_id
    _validate_provider_key_reference(provider, target_kms_key_id)

    key_version = await _next_key_version(db, model_id)
    raw_data_key = Fernet.generate_key().decode("ascii")
    wrapped_key = _wrap_data_key(
        raw_data_key=raw_data_key,
        kms_provider=provider,
        kms_key_id=target_kms_key_id,
    )

    new_key = ModelEncryptionKey(
        model_id=model_id,
        key_version=key_version,
        kms_provider=provider,
        kms_key_id=target_kms_key_id,
        wrapped_key=wrapped_key,
        is_active=True,
    )
    db.add(new_key)
    await db.flush()
    await _reencrypt_model_cells(db, model_id, new_key)

    keys = await list_model_encryption_keys(db, model_id)
    for key in keys:
        key.is_active = key.id == new_key.id

    await db.commit()
    await db.refresh(new_key)
    clear_model_encryption_key_cache()
    return new_key
