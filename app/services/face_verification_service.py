from __future__ import annotations

from math import sqrt
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import BadRequestException


class FaceVerificationService:
    def verify_profile_vs_selfie(self, *, profile_image_path: str, selfie_image_path: str) -> float:
        profile_path = Path(profile_image_path)
        selfie_path = Path(selfie_image_path)
        if not profile_path.exists() or not profile_path.is_file():
            raise BadRequestException("Profile image file does not exist")
        if not selfie_path.exists() or not selfie_path.is_file():
            raise BadRequestException("Selfie image file does not exist")

        profile_bytes = profile_path.read_bytes()
        selfie_bytes = selfie_path.read_bytes()

        self._validate_image_bytes(profile_bytes, profile_path.name)
        self._validate_image_bytes(selfie_bytes, selfie_path.name)

        provider = settings.attendance_face_provider.strip().lower()
        if provider == "aws_rekognition":
            return self._verify_with_aws(profile_bytes=profile_bytes, selfie_bytes=selfie_bytes)
        if provider == "local":
            return self._verify_with_local(profile_bytes=profile_bytes, selfie_bytes=selfie_bytes)
        raise BadRequestException("Unsupported face verification provider configuration")

    def _verify_with_aws(self, *, profile_bytes: bytes, selfie_bytes: bytes) -> float:
        try:
            import boto3  # type: ignore
        except ModuleNotFoundError as exc:
            raise BadRequestException("boto3 is required for aws_rekognition provider") from exc

        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise BadRequestException("AWS credentials are not configured for face verification")

        client = boto3.client(
            "rekognition",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        try:
            response = client.compare_faces(
                SourceImage={"Bytes": profile_bytes},
                TargetImage={"Bytes": selfie_bytes},
                SimilarityThreshold=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            raise BadRequestException(f"Face verification failed: {exc}") from exc

        matches = response.get("FaceMatches", [])
        if not matches:
            return 0.0
        best_similarity = max(float(item.get("Similarity", 0.0)) for item in matches)
        return round(best_similarity / 100.0, 4)

    def _verify_with_local(self, *, profile_bytes: bytes, selfie_bytes: bytes) -> float:
        histogram_score = self._cosine_similarity(
            self._byte_histogram(profile_bytes),
            self._byte_histogram(selfie_bytes),
        )
        locality_score = self._jaccard_similarity(
            self._rolling_chunk_hashes(profile_bytes),
            self._rolling_chunk_hashes(selfie_bytes),
        )
        return float(round(0.65 * histogram_score + 0.35 * locality_score, 4))

    @staticmethod
    def _validate_image_bytes(binary: bytes, name: str) -> None:
        if len(binary) < 1024:
            raise BadRequestException(f"Invalid image content: {name}")
        image_type = FaceVerificationService._detect_image_type(binary)
        if image_type not in {"jpeg", "png", "webp"}:
            raise BadRequestException(f"Unsupported image type: {name}")

    @staticmethod
    def _detect_image_type(binary: bytes) -> str | None:
        if binary.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if binary.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if len(binary) >= 12 and binary.startswith(b"RIFF") and binary[8:12] == b"WEBP":
            return "webp"
        return None

    @staticmethod
    def _byte_histogram(binary: bytes) -> list[float]:
        histogram = [0] * 256
        for item in binary:
            histogram[item] += 1
        length = len(binary)
        return [count / length for count in histogram]

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = sqrt(sum(a * a for a in vec1))
        norm2 = sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm1 * norm2)))

    @staticmethod
    def _rolling_chunk_hashes(binary: bytes, *, chunk_size: int = 128, step: int = 64) -> set[int]:
        if len(binary) <= chunk_size:
            return {hash(binary)}
        hashes: set[int] = set()
        max_windows = 3000
        windows = 0
        for index in range(0, len(binary) - chunk_size + 1, step):
            hashes.add(hash(binary[index : index + chunk_size]))
            windows += 1
            if windows >= max_windows:
                break
        return hashes

    @staticmethod
    def _jaccard_similarity(set1: set[int], set2: set[int]) -> float:
        if not set1 and not set2:
            return 1.0
        union = set1 | set2
        if not union:
            return 0.0
        intersection = set1 & set2
        return len(intersection) / len(union)
