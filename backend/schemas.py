from pydantic import BaseModel, ConfigDict, Field


class Observations(BaseModel):
    earth: str = Field(max_length=700)
    human: str = Field(max_length=700)
    heaven: str = Field(max_length=700)
    jade: str = Field(max_length=700)
    family: str = Field(max_length=700)


class BilingualAnalysis(BaseModel):
    foundation: str = Field(min_length=100, max_length=150)
    wisdom: str = Field(min_length=100, max_length=150)
    karma: str = Field(min_length=100, max_length=150)
    career: str = Field(min_length=100, max_length=150)
    marriage: str = Field(min_length=100, max_length=150)


class Analysis(BaseModel):
    classical: BilingualAnalysis
    modern: BilingualAnalysis


class TimelineStage(BaseModel):
    title: str = Field(max_length=120)
    classical: str = Field(min_length=100, max_length=150)
    modern: str = Field(min_length=100, max_length=150)


class Timeline(BaseModel):
    early_years: TimelineStage
    middle_years: TimelineStage
    later_years: TimelineStage


class PalmistryReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    observations: Observations
    analysis: Analysis
    timeline: Timeline
    master_pan_ci: str = Field(min_length=2, max_length=100)
    disclaimer: str = "本卷轴由 AI 结合传统易理相学生成，仅供国学文化交流与雅玩，不作现代医学或人生决策之用。"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    request_id: str
    error: ErrorBody
