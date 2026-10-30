"""
Mock portal for local development and testing.
Returns realistic fake data so the full BOB pipeline can be tested without a real browser.
"""
from datetime import date
from portals.base import BasePortal
from core.bob_report import BOBReport
from core.benefit_parser import build_benefit


class MockPortal(BasePortal):

    PORTAL_NAME = "Mock Portal"
    PORTAL_URL = "http://localhost"

    async def login(self, credentials: dict) -> None:
        pass  # No browser needed

    async def navigate_to_eligibility(self, patient: dict) -> None:
        pass

    async def extract_bob(self) -> dict:
        return {
            "coverage_status": "Active",
            "subscriber_id": "UC123456789",
            "group_number": "GRP-00123",
            "plan_name": "United Concordia TRICARE Dental Program",
            "effective_date": "01/01/2024",
            "annual_max": "$2,000.00",
            "deductible_amount": "$50.00",
            "deductible_used": "$25.00",
            "benefits": [
                {"code": "D0120", "description": "Periodic Oral Evaluation",     "frequency": "Twice per calendar year", "last_service": "03/15/2026"},
                {"code": "D1110", "description": "Prophylaxis - Adult",           "frequency": "Once every 6 months",     "last_service": "03/15/2026"},
                {"code": "D1120", "description": "Prophylaxis - Child",           "frequency": "Once every 6 months",     "last_service": ""},
                {"code": "D1206", "description": "Topical Fluoride Varnish",      "frequency": "Twice per calendar year", "last_service": "03/15/2026"},
                {"code": "D1260", "description": "Topical Fluoride - Child",      "frequency": "Once every 6 months",     "last_service": "01/10/2026"},
                {"code": "D2740", "description": "Crown - Porcelain/Ceramic",     "frequency": "Once every 5 years",      "last_service": "06/01/2023"},
                {"code": "D4910", "description": "Periodontal Maintenance",       "frequency": "Once every 3 months",     "last_service": "08/01/2026"},
            ],
        }

    def build_report(self, raw: dict, patient: dict) -> BOBReport:
        from portals.united_concordia import UnitedConcordiaPortal
        # Reuse UC's build_report logic since data shape is identical
        uc = UnitedConcordiaPortal.__new__(UnitedConcordiaPortal)
        report = uc.build_report(raw, patient)
        report.portal = self.PORTAL_NAME
        return report
