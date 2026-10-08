from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["scheduled", "completed", "cancelled"]


class DoctorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    specialty: str = Field(min_length=2, max_length=80)


class DoctorOut(DoctorCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AppointmentCreate(BaseModel):
    patient_name: str = Field(min_length=2, max_length=120)
    patient_phone: str | None = Field(default=None, max_length=32)
    doctor_id: int
    scheduled_at: datetime
    reason: str | None = Field(default=None, max_length=500)


class AppointmentUpdate(BaseModel):
    patient_name: str | None = Field(default=None, min_length=2, max_length=120)
    patient_phone: str | None = Field(default=None, max_length=32)
    doctor_id: int | None = None
    scheduled_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)
    status: Status | None = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_name: str
    patient_phone: str | None
    doctor_id: int
    doctor: DoctorOut
    scheduled_at: datetime
    reason: str | None
    status: Status
    created_at: datetime


class Stats(BaseModel):
    total: int
    scheduled: int
    completed: int
    cancelled: int
    today: int
    doctors: int
