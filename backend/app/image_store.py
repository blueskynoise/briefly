import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class StoredImage:
    content: bytes
    content_type: str
    expires_at: datetime


class TemporaryImageStore:
    def __init__(self) -> None:
        self._images: dict[str, StoredImage] = {}

    def put(self, content: bytes, content_type: str = "image/png", ttl_minutes: int = 15) -> str:
        image_id = secrets.token_urlsafe(24)
        self._images[image_id] = StoredImage(
            content=content,
            content_type=content_type,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
        return image_id

    def get(self, image_id: str) -> StoredImage | None:
        image = self._images.get(image_id)
        if not image:
            return None
        if image.expires_at <= datetime.now(timezone.utc):
            self._images.pop(image_id, None)
            return None
        return image
