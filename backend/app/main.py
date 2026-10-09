from datetime import datetime, time, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .config import settings
from .db import get_db

app = FastAPI(title="ClinicQ API", version="1.0.0", description="Clinic appointment booking service")

APPOINTMENTS_BOOKED = Counter(
    "clinicq_appointments_booked_total", "Appointments booked through the API"
)
APPOINTMENTS_CANCELLED = Counter(
    "clinicq_appointments_cancelled_total", "Appointments cancelled through the API"
)

Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/health", "/ready"],
).instrument(app).expose(app, include_in_schema=False)


# ---------- platform endpoints ----------
@app.get("/", tags=["platform"])
def root():
    return {"service": settings.app_name, "docs": "/docs", "status": "ok"}


@app.get("/health", tags=["platform"])
def health():
    """Liveness: the process is up."""
    return {"status": "OK"}


@app.get("/ready", tags=["platform"])
def ready(response: Response, db: Session = Depends(get_db)):
    """Readiness: the database answers."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return {"status": "NOT_READY"}
    return {"status": "READY"}


# ---------- doctors ----------
@app.get("/api/doctors", response_model=list[schemas.DoctorOut], tags=["doctors"])
def list_doctors(db: Session = Depends(get_db)):
    return db.scalars(select(models.Doctor).order_by(models.Doctor.name)).all()


@app.post("/api/doctors", response_model=schemas.DoctorOut, status_code=201, tags=["doctors"])
def create_doctor(payload: schemas.DoctorCreate, db: Session = Depends(get_db)):
    doctor = models.Doctor(**payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@app.delete("/api/doctors/{doctor_id}", status_code=204, tags=["doctors"])
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.get(models.Doctor, doctor_id)
    if not doctor:
        raise HTTPException(404, "Doctor not found")
    booked = db.scalar(
        select(func.count()).select_from(models.Appointment).where(models.Appointment.doctor_id == doctor_id)
    )
    if booked:
        raise HTTPException(409, "Doctor still has appointments")
    db.delete(doctor)
    db.commit()


# ---------- appointments ----------
def _require_doctor(db: Session, doctor_id: int) -> None:
    if not db.get(models.Doctor, doctor_id):
        raise HTTPException(422, f"Doctor {doctor_id} does not exist")


def _slot_taken(db: Session, doctor_id: int, when: datetime, exclude_id: int | None = None) -> bool:
    query = select(models.Appointment.id).where(
        models.Appointment.doctor_id == doctor_id,
        models.Appointment.scheduled_at == when,
        models.Appointment.status != "cancelled",
    )
    if exclude_id is not None:
        query = query.where(models.Appointment.id != exclude_id)
    return db.scalar(query) is not None


@app.get("/api/appointments/stats", response_model=schemas.Stats, tags=["appointments"])
def stats(db: Session = Depends(get_db)):
    by_status = dict(
        db.execute(select(models.Appointment.status, func.count()).group_by(models.Appointment.status)).all()
    )
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    today_count = db.scalar(
        select(func.count()).select_from(models.Appointment).where(
            models.Appointment.scheduled_at.between(start, end),
            models.Appointment.status != "cancelled",
        )
    )
    return schemas.Stats(
        total=sum(by_status.values()),
        scheduled=by_status.get("scheduled", 0),
        completed=by_status.get("completed", 0),
        cancelled=by_status.get("cancelled", 0),
        today=today_count or 0,
        doctors=db.scalar(select(func.count()).select_from(models.Doctor)) or 0,
    )


@app.get("/api/appointments", response_model=list[schemas.AppointmentOut], tags=["appointments"])
def list_appointments(
    status: schemas.Status | None = None,
    doctor_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = (
        select(models.Appointment)
        .options(joinedload(models.Appointment.doctor))
        .order_by(models.Appointment.scheduled_at)
        .limit(limit)
    )
    if status:
        query = query.where(models.Appointment.status == status)
    if doctor_id:
        query = query.where(models.Appointment.doctor_id == doctor_id)
    return db.scalars(query).all()


@app.get("/api/appointments/{appointment_id}", response_model=schemas.AppointmentOut, tags=["appointments"])
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    return appt


@app.post("/api/appointments", response_model=schemas.AppointmentOut, status_code=201, tags=["appointments"])
def create_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    _require_doctor(db, payload.doctor_id)
    if _slot_taken(db, payload.doctor_id, payload.scheduled_at):
        raise HTTPException(409, "That time slot is already booked for this doctor")
    appt = models.Appointment(**payload.model_dump())
    db.add(appt)
    db.commit()
    db.refresh(appt)
    APPOINTMENTS_BOOKED.inc()
    return appt


@app.put("/api/appointments/{appointment_id}", response_model=schemas.AppointmentOut, tags=["appointments"])
def update_appointment(appointment_id: int, payload: schemas.AppointmentUpdate, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    changes = payload.model_dump(exclude_unset=True)
    doctor_id = changes.get("doctor_id", appt.doctor_id)
    when = changes.get("scheduled_at", appt.scheduled_at)
    new_status = changes.get("status", appt.status)
    if "doctor_id" in changes:
        _require_doctor(db, doctor_id)
    moving = "doctor_id" in changes or "scheduled_at" in changes or appt.status == "cancelled"
    if new_status != "cancelled" and moving and _slot_taken(db, doctor_id, when, exclude_id=appt.id):
        raise HTTPException(409, "That time slot is already booked for this doctor")
    if new_status == "cancelled" and appt.status != "cancelled":
        APPOINTMENTS_CANCELLED.inc()
    for key, value in changes.items():
        setattr(appt, key, value)
    db.commit()
    db.refresh(appt)
    return appt


@app.delete("/api/appointments/{appointment_id}", status_code=204, tags=["appointments"])
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    db.delete(appt)
    db.commit()
