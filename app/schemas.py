from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    name: str
    password: str


class MeResponse(BaseModel):
    name: str


class ConfigResponse(BaseModel):
    accounts: list[str]
    recommended_models: list[str]
    default_model: str
    default_retries: int


class RunCreateRequest(BaseModel):
    assessment_url: str
    headless: bool = True
    test_account_label: str = "Default"
    model: Optional[str] = None
    max_retries: int = Field(default=2, ge=1, le=5)


class RunCreateResponse(BaseModel):
    id: str


class RunView(BaseModel):
    id: str
    assessment_url: str
    headless: bool
    test_account_label: str
    model: str
    max_retries: int
    output_dir: str
    status: str
    error: Optional[str] = None
    created_by: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    created_at_fmt: Optional[str] = None
    started_at_fmt: Optional[str] = None
    finished_at_fmt: Optional[str] = None
    queue_position: Optional[int] = None
    telemetry: Optional[dict[str, Any]] = None
