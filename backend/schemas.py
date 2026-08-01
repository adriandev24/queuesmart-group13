"""Pydantic request schemas and validation rules."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class RegisterRequest(StrictModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Literal["user", "administrator"]
    contact_info: str | None = Field(default=None, max_length=120)
    preferences: str | None = Field(default=None, max_length=250)


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class ProfileUpdateRequest(StrictModel):
    full_name: str = Field(min_length=2, max_length=80)
    contact_info: str | None = Field(default=None, max_length=120)
    preferences: str | None = Field(default=None, max_length=250)


class ServiceCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=250)
    expected_duration: int = Field(ge=1, le=120)
    priority_level: Literal["low", "medium", "high"]


class ServiceUpdateRequest(ServiceCreateRequest):
    pass


class QueueJoinRequest(StrictModel):
    service_id: int = Field(gt=0)
    reason_for_visit: str = Field(min_length=2, max_length=200)


class MoveQueueEntryRequest(StrictModel):
    position: int = Field(ge=1)
