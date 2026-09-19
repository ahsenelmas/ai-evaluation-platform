from pydantic import BaseModel, Field, field_validator


class CreateHumanReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    category: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @field_validator("reviewer", "category", "explanation")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value
