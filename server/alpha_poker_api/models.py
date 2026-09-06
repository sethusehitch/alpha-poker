from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    invite_code: str | None = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class TrainingCreate(BaseModel):
    username: str = Field(default="local", min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    opponent: Literal["leader"] = "leader"
    hand_limit: int = Field(default=5000, ge=1, le=10000)
    client_schema_version: Literal["2026-09-01"] = "2026-09-01"


class RunCreate(BaseModel):
    # Duplicate-deal matches are scheduled in mirrored pairs, so an odd hand
    # count cannot be fulfilled without silently changing the request.
    hand_count_per_pairing: int = Field(default=2000, ge=2, le=100000, multiple_of=2)
    seed: int | None = None


# Feature-request title/details and feedback message limits are enforced in
# main/community route bodies (not here) so violations return the community
# surfaces' documented 400 validation_error copy instead of a generic 422.
# These Field bounds are only a generous backstop against oversized payloads.
class FeatureRequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=4000)
    details: str | None = Field(default=None, max_length=4000)


class FeatureRequestVote(BaseModel):
    value: Literal[1, 0, -1]


class FeatureRequestStatusUpdate(BaseModel):
    status: Literal["submitted", "under_review", "planned", "in_progress", "shipped", "declined"]


class FeatureRequestHide(BaseModel):
    hidden: bool


class FeedbackCreate(BaseModel):
    type: Literal["bug", "idea", "other"]
    message: str = Field(min_length=1, max_length=4000)
    path: str = Field(min_length=1, max_length=500)
