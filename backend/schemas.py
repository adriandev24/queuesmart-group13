import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)
    role: Literal["user", "administrator"] = "user"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    contact_info: str | None = Field(default=None, max_length=120)
    preferences: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def require_change(self):
        if self.full_name is None and self.contact_info is None and self.preferences is None:
            raise ValueError("Provide at least one profile field to update")
        return self


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=250)
    expected_duration: int = Field(ge=1, le=120)
    priority_level: Literal["low", "medium", "high"]


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=5, max_length=250)
    expected_duration: int | None = Field(default=None, ge=1, le=120)
    priority_level: Literal["low", "medium", "high"] | None = None

    @model_validator(mode="after")
    def require_change(self):
        if all(value is None for value in (self.name, self.description, self.expected_duration, self.priority_level)):
            raise ValueError("Provide at least one service field to update")
        return self


class QueueJoinRequest(BaseModel):
    service_id: int = Field(gt=0)
    reason_for_visit: str = Field(min_length=2, max_length=200)


class MoveRequest(BaseModel):
    direction: Literal["up", "down"]
