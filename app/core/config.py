from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "FastAPI RBAC"
    app_env: str = "development"
    database_url: str = "mysql+pymysql://root:root@localhost:3306/fastapi_rbac"
    jwt_secret_key: str = Field(default="change-this-secret-in-production")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    cors_allowed_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allowed_methods: list[str] = ["*"]
    cors_allowed_headers: list[str] = ["*"]
    upload_root_dir: str = "storage/uploads"
    max_file_size_bytes: int = 5 * 1024 * 1024
    attendance_max_distance_meters: int = 300
    attendance_face_match_threshold: float = 0.75
    attendance_face_provider: str = "aws_rekognition"
    aws_region: str = "ap-south-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    cors_allowed_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    cors_allowed_methods = [
        method.strip()
        for method in os.getenv("CORS_ALLOWED_METHODS", "*").split(",")
        if method.strip()
    ]
    cors_allowed_headers = [
        header.strip()
        for header in os.getenv("CORS_ALLOWED_HEADERS", "*").split(",")
        if header.strip()
    ]

    return Settings(
        app_name=os.getenv("APP_NAME", "FastAPI RBAC"),
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv(
            "DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/fastapi_rbac"
        ),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-this-secret-in-production"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        cors_allowed_origins=cors_allowed_origins or ["*"],
        cors_allow_credentials=os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true",
        cors_allowed_methods=cors_allowed_methods or ["*"],
        cors_allowed_headers=cors_allowed_headers or ["*"],
        upload_root_dir=os.getenv("UPLOAD_ROOT_DIR", "storage/uploads"),
        max_file_size_bytes=int(os.getenv("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024))),
        attendance_max_distance_meters=int(os.getenv("ATTENDANCE_MAX_DISTANCE_METERS", "300")),
        attendance_face_match_threshold=float(os.getenv("ATTENDANCE_FACE_MATCH_THRESHOLD", "0.75")),
        attendance_face_provider=os.getenv("ATTENDANCE_FACE_PROVIDER", "aws_rekognition"),
        aws_region=os.getenv("AWS_REGION", "ap-south-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


settings = get_settings()
