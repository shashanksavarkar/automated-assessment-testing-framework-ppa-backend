from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class MeResponse(BaseModel):
    email: str


class ModelStat(BaseModel):
    model: str
    runs: int
    coding_questions: int
    success_rate: Optional[float] = None  # fraction 0-1; None if no CODING data observed yet


class ConfigResponse(BaseModel):
    accounts: list[str]
    recommended_models: list[str]
    model_stats: list[ModelStat]
    default_model: str
    default_retries: int


class CustomAccount(BaseModel):
    email: str
    name: str = "BOT"
    mobile: str = "9999999999"
    roll_number: str = "9988774455"


class RunCreateRequest(BaseModel):
    assessment_url: str
    headless: bool = True
    test_account_label: str = "Default"
    custom_account: Optional[CustomAccount] = None
    model: Optional[str] = None
    max_retries: int = Field(default=2, ge=1, le=5)
    note: Optional[str] = None


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
    note: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    created_at_fmt: Optional[str] = None
    started_at_fmt: Optional[str] = None
    finished_at_fmt: Optional[str] = None
    queue_position: Optional[int] = None
    telemetry: Optional[dict[str, Any]] = None
