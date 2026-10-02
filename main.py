import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# PYDANTIC MODELS (Data Schemas & Validation)
# -------------------------------------------------------------------

class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class Contact(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None


class EmergencyContact(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None


class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str


class Doctor(BaseModel):
    doctor_id: str
    name: str
    facility: str


class MedicalProfile(BaseModel):
    allergies: List[str] = Field(default_factory=list)
    chronic_conditions: List[str] = Field(default_factory=list)
    current_medications: List[Medication] = Field(default_factory=list)
    primary_care_physician: Optional[Doctor] = None
    recent_vitals: Optional[List[dict]] = None


class Vitals(BaseModel):
    blood_pressure: Optional[str] = None
    heart_rate_bpm: Optional[int] = None
    temperature_celsius: Optional[float] = None
    weight_kg: Optional[float] = None


class Visit(BaseModel):
    visit_id: str
    visit_date: str
    reason_for_visit: str
    vitals: Optional[Vitals] = None


class Patient(BaseModel):
    patient_id: str = Field(..., pattern=r"^P-\d{6}$", description="Patient ID pattern: P-XXXXXX")
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    blood_type: Optional[str] = None
    contact: Optional[Contact] = None
    emergency_contact: Optional[EmergencyContact] = None
    medical_profile: Optional[MedicalProfile] = None
    recent_visits: List[Visit] = Field(default_factory=list)


class PatientCreate(BaseModel):
    patient_id: str = Field(..., pattern=r"^P-\d{6}$", description="Patient ID pattern: P-XXXXXX")
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    blood_type: Optional[str] = None
    contact: Optional[Contact] = None
    emergency_contact: Optional[EmergencyContact] = None
    medical_profile: Optional[MedicalProfile] = None


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    contact: Optional[Contact] = None
    emergency_contact: Optional[EmergencyContact] = None
    medical_profile: Optional[MedicalProfile] = None


class PatientMedicalProfileResponse(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    medical_profile: MedicalProfile


class HomeResponse(BaseModel):
    message: str
    version: str
    documentation: str


class AboutResponse(BaseModel):
    app_name: str
    description: str
    author: str
    status: str


# -------------------------------------------------------------------
# FASTAPI APP & HELPER FUNCTIONS
# -------------------------------------------------------------------

app = FastAPI(title="Patient Management API")


def load_patients_data():
    """Reads JSON file and returns the list of raw patient dictionaries and format flag."""
    try:
        with open("patients.json", "r") as file:
            data = json.load(file)
        if isinstance(data, dict) and "patients" in data:
            return data["patients"], True
        return (data if isinstance(data, list) else []), False
    except FileNotFoundError:
        return [], False


def save_patients_data(patients_list: list, is_wrapped: bool):
    """Writes updated patient list back to patients.json."""
    with open("patients.json", "w") as file:
        if is_wrapped:
            json.dump({"patients": patients_list}, file, indent=2)
        else:
            json.dump(patients_list, file, indent=2)


# -------------------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------------------

# 1. HOME ENDPOINT
@app.get("/", response_model=HomeResponse)
def home():
    return HomeResponse(
        message="Welcome to the Patient Management API!",
        version="1.0.0",
        documentation="/docs"
    )


# 2. ABOUT ENDPOINT
@app.get("/about", response_model=AboutResponse)
def about():
    return AboutResponse(
        app_name="Patient Management System",
        description="A FastAPI application using Pydantic models for data validation.",
        author="API Developer",
        status="Active"
    )


# 3. GET ALL PATIENTS
@app.get("/patients", response_model=List[Patient])
def get_all_patients(
    gender: Optional[str] = Query(None, description="Filter patients by gender"),
    limit: int = Query(10, ge=1, le=50, description="Number of patients to return")
):
    raw_data, _ = load_patients_data()

    if gender:
        raw_data = [p for p in raw_data if p.get("gender", "").lower() == gender.lower()]

    return [Patient(**p) for p in raw_data[:limit]]


# 4. GET SINGLE PATIENT BY ID
@app.get("/patients/{patient_id}", response_model=Patient)
def get_patient_by_id(
    patient_id: str = Path(
        ...,
        title="Patient ID",
        description="The unique identifier for the patient (e.g., P-100293)",
        pattern=r"^P-\d{6}$"
    )
):
    raw_data, _ = load_patients_data()
    for item in raw_data:
        if item.get("patient_id") == patient_id:
            return Patient(**item)
            
    raise HTTPException(status_code=404, detail="Patient not found")


# 5. COMBINED PATH & QUERY PARAMETERS ENDPOINT
@app.get("/patients/{patient_id}/medical-profile", response_model=PatientMedicalProfileResponse)
def get_patient_medical_profile(
    patient_id: str = Path(
        ...,
        title="Patient ID",
        pattern=r"^P-\d{6}$",
        description="Path Parameter: Identifies the specific patient"
    ),
    include_vitals: bool = Query(
        False,
        description="Query Parameter: Set to true to include recent visit vitals"
    )
):
    raw_data, _ = load_patients_data()
    
    for item in raw_data:
        if item.get("patient_id") == patient_id:
            patient = Patient(**item)
            medical_profile = patient.medical_profile or MedicalProfile()
            
            if include_vitals and patient.recent_visits:
                vitals_list = [
                    visit.vitals.model_dump()
                    for visit in patient.recent_visits 
                    if visit.vitals is not None
                ]
                medical_profile.recent_vitals = vitals_list

            return PatientMedicalProfileResponse(
                patient_id=patient.patient_id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                medical_profile=medical_profile
            )

    raise HTTPException(status_code=404, detail="Patient not found")


# 6. POST ENDPOINT (Create Patient)
@app.post("/patients", response_model=Patient, status_code=status.HTTP_201_CREATED)
def create_patient(new_patient: PatientCreate):
    raw_data, is_wrapped = load_patients_data()

    for item in raw_data:
        if item.get("patient_id") == new_patient.patient_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Patient with ID {new_patient.patient_id} already exists"
            )

    patient_dict = new_patient.model_dump()
    patient_dict["recent_visits"] = []

    raw_data.append(patient_dict)
    save_patients_data(raw_data, is_wrapped)

    return Patient(**patient_dict)


# 7. PUT ENDPOINT (Update Patient)
@app.put("/patients/{patient_id}", response_model=Patient)
def update_patient(
    patient_update: PatientUpdate,
    patient_id: str = Path(..., pattern=r"^P-\d{6}$")
):
    raw_data, is_wrapped = load_patients_data()

    for index, item in enumerate(raw_data):
        if item.get("patient_id") == patient_id:
            # Extract provided fields (excluding unset fields)
            update_data = patient_update.model_dump(exclude_unset=True)

            # Update patient record with new data
            item.update(update_data)
            raw_data[index] = item 

            # Persist changes back to file
            save_patients_data(raw_data, is_wrapped)
            return Patient(**item)

    raise HTTPException(status_code=404, detail="Patient not found")


# 8. DELETE ENDPOINT (Delete Patient)
@app.delete("/patients/{patient_id}")
def delete_patient(
    patient_id: str = Path(..., pattern=r"^P-\d{6}$")
):
    raw_data, is_wrapped = load_patients_data()

    for index, item in enumerate(raw_data):
        if item.get("patient_id") == patient_id:
            # Remove item from list
            deleted_patient = raw_data.pop(index)

            # Persist updated list
            save_patients_data(raw_data, is_wrapped)
            return {
                "message": f"Patient {patient_id} has been successfully deleted",
                "deleted_patient_id": deleted_patient.get("patient_id")
            }

    raise HTTPException(status_code=404, detail="Patient not found")