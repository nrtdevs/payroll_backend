from __future__ import annotations

import base64
import io
import json

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.exceptions import BadRequestException


class FaceVerificationService:
    def extract_face_encoding(self, image_base64: str) -> list[float]:
        frame = self._decode_image_from_base64(image_base64=image_base64)
        return self._extract_single_face_encoding(frame)

    def extract_face_encoding_from_bytes(self, image_bytes: bytes) -> list[float]:
        frame = self._decode_image_from_bytes(image_bytes=image_bytes)
        return self._extract_single_face_encoding(frame)

    def _extract_single_face_encoding(self, frame: np.ndarray) -> list[float]:
        face_recognition = self._face_lib()
        locations = face_recognition.face_locations(frame)
        if len(locations) != 1:
            raise BadRequestException("Exactly one face is required")
        encodings = face_recognition.face_encodings(frame, known_face_locations=locations)
        if len(encodings) != 1:
            raise BadRequestException("Unable to generate face encoding")
        return [float(item) for item in encodings[0].tolist()]

    def compare_face_encodings(self, *, stored: list[float], live: list[float]) -> tuple[float, float]:
        if len(stored) != 128 or len(live) != 128:
            raise BadRequestException("Invalid face encoding length")
        face_recognition = self._face_lib()
        distance = float(
            face_recognition.face_distance(
                np.array([stored], dtype=np.float64),
                np.array(live, dtype=np.float64),
            )[0]
        )
        confidence = max(0.0, min(1.0, 1.0 - distance))
        return distance, confidence

    @staticmethod
    def serialize_encoding(encoding: list[float]) -> str:
        return json.dumps(encoding)

    @staticmethod
    def deserialize_encoding(encoded: str) -> list[float]:
        try:
            parsed = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise BadRequestException("Stored face encoding is invalid") from exc
        if not isinstance(parsed, list) or len(parsed) != 128:
            raise BadRequestException("Stored face encoding is invalid")
        try:
            return [float(item) for item in parsed]
        except (TypeError, ValueError) as exc:
            raise BadRequestException("Stored face encoding is invalid") from exc

    def _decode_image_from_base64(self, *, image_base64: str) -> np.ndarray:
        if not image_base64 or not image_base64.strip():
            raise BadRequestException("image_base64 is required")
        payload = image_base64.strip()
        if "," in payload and payload.lower().startswith("data:image"):
            payload = payload.split(",", 1)[1]

        try:
            binary = base64.b64decode(payload, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise BadRequestException("Invalid base64 image payload") from exc

        return self._decode_image_from_bytes(image_bytes=binary)

    def _decode_image_from_bytes(self, *, image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise BadRequestException("Image is required")
        binary = image_bytes
        if len(binary) > settings.max_file_size_bytes:
            raise BadRequestException("Image exceeds max allowed size")

        try:
            image = Image.open(io.BytesIO(binary))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise BadRequestException("Invalid image content") from exc

        rgb = image.convert("RGB")
        return np.asarray(rgb)

    @staticmethod
    def _face_lib():
        try:
            import face_recognition  # type: ignore
        except ModuleNotFoundError as exc:
            raise BadRequestException("face_recognition dependency is not installed") from exc
        return face_recognition
