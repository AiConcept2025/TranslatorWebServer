"""
JSON serialization utilities for MongoDB documents.

Handles conversion of:
- datetime → ISO 8601 string
- ObjectId → string
- Decimal128 → float
"""

from datetime import datetime
from typing import Any
from bson import ObjectId
from bson.decimal128 import Decimal128
import logging

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any, *, _path: str = "root") -> Any:
    """
    Recursively serialize MongoDB documents for JSON responses.

    Converts:
    - datetime objects → ISO 8601 strings
    - ObjectId objects → hex strings
    - Decimal128 objects → floats
    - dict values (recursively)
    - list items (recursively)

    Args:
        obj: Object to serialize (dict, list, datetime, ObjectId, Decimal128, primitive)
        _path: Internal tracking of object path (for logging)

    Returns:
        JSON-serializable object

    Example:
        >>> from datetime import datetime, timezone
        >>> doc = {
        ...     "_id": ObjectId("507f1f77bcf86cd799439011"),
        ...     "created_at": datetime.now(timezone.utc),
        ...     "amount": Decimal128("123.45"),
        ...     "items": [{"date": datetime.now(timezone.utc)}]
        ... }
        >>> serialized = serialize_for_json(doc)
        >>> assert isinstance(serialized["_id"], str)
        >>> assert isinstance(serialized["created_at"], str)
        >>> assert isinstance(serialized["amount"], float)
    """
    if isinstance(obj, datetime):
        # Convert datetime to ISO 8601 string
        iso_str = obj.isoformat()
        logger.debug(f"[SERIALIZATION] {_path}: datetime → '{iso_str}'")
        return iso_str

    elif isinstance(obj, ObjectId):
        # Convert ObjectId to hex string
        str_val = str(obj)
        logger.debug(f"[SERIALIZATION] {_path}: ObjectId → '{str_val}'")
        return str_val

    elif isinstance(obj, Decimal128):
        # Convert Decimal128 to float
        float_val = float(obj.to_decimal())
        logger.debug(f"[SERIALIZATION] {_path}: Decimal128 → {float_val}")
        return float_val

    elif isinstance(obj, dict):
        # Recursively process dictionary
        return {
            key: serialize_for_json(value, _path=f"{_path}.{key}")
            for key, value in obj.items()
        }

    elif isinstance(obj, list):
        # Recursively process list
        return [
            serialize_for_json(item, _path=f"{_path}[{i}]")
            for i, item in enumerate(obj)
        ]

    else:
        # Primitive type (str, int, float, bool, None) - return as-is
        return obj
