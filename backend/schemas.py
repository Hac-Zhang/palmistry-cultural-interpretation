from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TechnicalMetrics(BaseModel):
    image_quality: Literal["High", "Medium", "Low"]
    confidence_score: int = Field(ge=0, le=100)


class Observations(BaseModel):
    earth_line: str = Field(max_length=700)
    human_line: str = Field(max_length=700)
    heaven_line: str = Field(max_length=700)
    jade_pillar_line: str = Field(max_length=700)
    family_ethos_line: str = Field(max_length=700)


class Analysis(BaseModel):
    foundation: str = Field(max_length=1200)
    wisdom: str = Field(max_length=1200)
    karma: str = Field(max_length=1200)
    career: str = Field(max_length=1200)
    marriage: str = Field(max_length=1200)


class PalmistryReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    technical_metrics: TechnicalMetrics
    observations: Observations
    analysis: Analysis
    master_pan_ci: str = Field(min_length=2, max_length=80)
    disclaimer: str = "本卷轴由 AI 结合传统易理相学生成，仅供国学文化交流与雅玩，不作现代医学或人生决策之用。"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    request_id: str
    error: ErrorBody
