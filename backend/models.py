from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["user", "administrator"]
Priority = Literal["low", "medium", "high"]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Role

    @field_validator("full_name")
    @classmethod
    def name_must_include_letters(cls, value: str) -> str:
        if not any(char.isalpha() for char in value):
            raise ValueError("Full name must contain letters")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Role


class ServiceCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=250)
    expected_duration: int = Field(ge=1, le=120)
    priority_level: Priority


class ServiceUpdateRequest(ServiceCreateRequest):
    pass


class JoinQueueRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    service_id: int = Field(gt=0)
    reason: str = Field(min_length=2, max_length=200)
