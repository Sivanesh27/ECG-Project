from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    confirm_password: str
    organization: Optional[str] = Field(default=None, max_length=160)
    role: Optional[str] = Field(default=None, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)
    remember: bool = False


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(max_length=256)


class DeleteAccountIn(BaseModel):
    password: str


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: float = Field(gt=0, lt=121)
    gender: Literal["male", "female", "other"] = "other"
    height_cm: Optional[float] = Field(default=None, gt=50, lt=260)
    weight_kg: Optional[float] = Field(default=None, gt=10, lt=400)
    resting_hr: Optional[float] = Field(default=None, gt=25, lt=140)
    max_hr: Optional[float] = Field(default=None, gt=100, lt=250)
    fitness_level: Optional[str] = Field(default=None, max_length=40)
    activity_type: Optional[str] = Field(default=None, max_length=80)
    exercise_duration_min: Optional[float] = Field(default=None, ge=0, lt=1500)
    notes: Optional[str] = Field(default=None, max_length=2000)


class ProcessIn(BaseModel):
    upload_id: str
    subject: SubjectIn
    session_keys: list[str] = Field(min_length=1, max_length=500)


class SettingsIn(BaseModel):
    hrmax_formula: Literal["220-age", "208-0.7age", "custom"] = "220-age"
    hrmax_custom: Optional[float] = Field(default=None, gt=100, lt=250)
    zones: list[list[float]] = [[0.5, 0.6], [0.6, 0.7], [0.7, 0.8], [0.8, 0.9], [0.9, 1.0]]
    filter: dict = {}
    artifact: dict = {}
    freq: dict = {}
    sampling_rate_override: Optional[float] = Field(default=None, gt=10, lt=5000)
    powerline_hz: Literal[50, 60] = 50

    @field_validator("zones")
    @classmethod
    def _zones(cls, z):
        if not (1 <= len(z) <= 8) or any(len(p) != 2 or not (0 < p[0] < p[1] <= 1.2) for p in z):
            raise ValueError("zones must be [lo, hi] fractions of HRmax with lo < hi")
        if any(z[i][1] > z[i + 1][0] + 1e-9 for i in range(len(z) - 1)):
            raise ValueError("zones must be ordered and non-overlapping")
        return z

    @field_validator("filter", "artifact", "freq")
    @classmethod
    def _allowed(cls, d, info):
        allow = {"filter": {"low_hz", "high_hz", "order", "powerline_hz", "notch_q", "notch_mode"},
                 "artifact": {"min_rr_ms", "max_rr_ms", "window", "jump_ratio", "short_ratio", "long_ratio", "mode"},
                 "freq": {"vlf", "lf", "hf", "method", "resample_hz", "welch_window_s", "min_total_s", "min_vlf_s"}}[info.field_name]
        bad = set(d) - allow
        if bad:
            raise ValueError(f"unknown keys: {sorted(bad)}")
        return d
