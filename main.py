import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

from core.credentials import get_credentials
from core.bob_report import BOBReport
from portals.united_concordia import UnitedConcordiaPortal

load_dotenv()
app = FastAPI(title="Dental Eligibility Automation")

PORTAL_MAP = {
    "united_concordia": (UnitedConcordiaPortal, os.getenv("AWS_SECRET_NAME_UC", "dental/united-concordia/credentials")),
    # "delta_dental": (DeltaDentalPortal, "dental/delta-dental/credentials"),  # add when ready
}


class VerifyRequest(BaseModel):
    portal: str          # e.g. "united_concordia"
    patient_name: str
    subscriber_id: str
    dob: str             # MM/DD/YYYY
    member_id: str | None = None


@app.post("/verify", response_model=BOBReport)
async def verify_eligibility(req: VerifyRequest):
    if req.portal not in PORTAL_MAP:
        raise HTTPException(400, f"Portal '{req.portal}' not supported. Available: {list(PORTAL_MAP)}")

    PortalClass, secret_name = PORTAL_MAP[req.portal]

    try:
        credentials = get_credentials(secret_name)
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve credentials: {e}")

    patient = {
        "name": req.patient_name,
        "subscriber_id": req.subscriber_id,
        "dob": req.dob,
        "member_id": req.member_id,
    }

    try:
        async with PortalClass(headless=True) as portal:
            report = await portal.run(credentials, patient)
    except RuntimeError as e:
        # Login failure, layout change, etc. — surface for human review
        raise HTTPException(422, str(e))

    return report


@app.get("/portals")
def list_portals():
    return {"supported": list(PORTAL_MAP.keys())}
