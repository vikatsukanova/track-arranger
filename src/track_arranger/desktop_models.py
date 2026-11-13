from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Loop(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    filename: str
    bpm: float = Field(ge=30, le=300)
    key: str = Field(max_length=32)
    bars: float = Field(ge=0.125, le=1024)
    seconds: float = Field(gt=0)


class Placement(BaseModel):
    lane: str = Field(min_length=1, max_length=80)
    loop_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')


class TimelineSection(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    name: str = Field(min_length=1, max_length=80)
    bars: int = Field(ge=8, le=256, multiple_of=8)
    clips: list[Placement] = Field(default_factory=list, max_length=32)

    @model_validator(mode='after')
    def unique_lanes(self):
        if len({c.lane for c in self.clips}) != len(self.clips):
            raise ValueError('Only one loop per lane in each section')
        return self


class Project(BaseModel):
    genre: Literal['dnb'] = 'dnb'
    bpm: float = Field(default=174, ge=160, le=180)
    sections: list[TimelineSection] = Field(min_length=1, max_length=64)
    loops: list[Loop] = Field(default_factory=list, max_length=128)

    @model_validator(mode='after')
    def unique_ids(self):
        for items in (self.sections, self.loops):
            if len({item.id for item in items}) != len(items):
                raise ValueError('IDs must be unique')
        if sum(s.bars for s in self.sections) > 2048:
            raise ValueError('Project cannot exceed 2048 bars')
        return self
