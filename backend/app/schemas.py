from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(Input):
    username: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9._-]+$')
    password: str = Field(min_length=1, max_length=128)

    @field_validator('username')
    @classmethod
    def normalize(cls, value):
        return value.lower()

    # Passwords must retain intentional spaces; override global string stripping.
    model_config = ConfigDict(extra='forbid')


class StudentCreate(Input):
    username: str | None = Field(default=None, min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9._-]+$')
    name: str = Field(min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    grade: str = Field(max_length=100)
    subject: str = Field(default='Mathematics', min_length=1, max_length=80)

    model_config = ConfigDict(extra='forbid')

    @field_validator('grade', mode='before')
    @classmethod
    def grade_label(cls, value):
        return str(value) if type(value) is int else value

    @field_validator('username')
    @classmethod
    def username_lower(cls, value):
        return value.lower() if value else value

    @model_validator(mode='after')
    def credentials_pair(self):
        if bool(self.username) != bool(self.password):
            raise ValueError('Provide both username and password, or leave both empty')
        return self

    @field_validator('name', 'subject')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('This field cannot be blank')
        return value.strip()


class Roster(Input):
    student_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator('student_ids')
    @classmethod
    def unique(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Students must be unique')
        return value


class BatchCreate(Roster):
    name: str = Field(min_length=1, max_length=120)


class ClassCreate(Roster):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(default='Mathematics', min_length=1, max_length=80)
    grade: str = Field(max_length=100)
    kind: Literal['ONE_TO_ONE', 'BATCH'] = 'ONE_TO_ONE'
    batch_id: str | None = None
    scheduled_at: datetime | None = None

    @field_validator('grade', mode='before')
    @classmethod
    def grade_label(cls, value):
        return str(value) if type(value) is int else value

    @model_validator(mode='after')
    def valid_class(self):
        if self.kind == 'ONE_TO_ONE' and (len(self.student_ids) != 1 or self.batch_id):
            raise ValueError('A 1-to-1 class requires exactly one student and no batch')
        if self.scheduled_at and self.scheduled_at.tzinfo is None:
            raise ValueError('Class time must include a timezone')
        return self


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
