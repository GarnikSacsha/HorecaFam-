from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictAssessmentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GenerationScope(StrictAssessmentSchema):
    organization_id: UUID
    location_id: UUID
    menu_version_id: UUID
    training_version_id: UUID
    lesson_version_id: UUID


class CategoryGenerationRule(StrictAssessmentSchema):
    code: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    mechanic: Literal["single_choice"] = "single_choice"


class CategoryFact(StrictAssessmentSchema):
    menu_item_version_id: UUID
    menu_item_id: UUID
    item_name: str
    menu_version_category_id: UUID
    category_name: str
    price_minor: int | None = Field(default=None, ge=0)
    verified: bool


class CandidateOption(StrictAssessmentSchema):
    stable_key: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=200)


class CandidatePromptPayload(StrictAssessmentSchema):
    locale: Literal["uk"] = "uk"
    stem: str = Field(min_length=1, max_length=500)
    options: list[CandidateOption] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def options_are_unambiguous(self) -> "CandidatePromptPayload":
        keys = [option.stable_key for option in self.options]
        labels = [option.text.casefold() for option in self.options]
        if len(keys) != len(set(keys)) or len(labels) != len(set(labels)):
            raise ValueError("Candidate options must be unique and unambiguous")
        return self


class CandidateAnswerPayload(StrictAssessmentSchema):
    correct_option_keys: list[str] = Field(min_length=1, max_length=20)


class CandidateExplanationPayload(StrictAssessmentSchema):
    locale: Literal["uk"] = "uk"
    text: str = Field(min_length=1, max_length=1000)


class CandidateSource(StrictAssessmentSchema):
    source_role: Literal["correct_fact", "distractor_basis", "explanation_source"]
    menu_item_version_id: UUID


class GeneratedCandidate(StrictAssessmentSchema):
    mechanic: Literal["single_choice"]
    prompt_payload: CandidatePromptPayload
    answer_payload: CandidateAnswerPayload
    explanation_payload: CandidateExplanationPayload
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: list[CandidateSource] = Field(min_length=2)
