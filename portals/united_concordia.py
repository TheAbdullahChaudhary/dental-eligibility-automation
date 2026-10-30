import re
from datetime import date
from playwright.async_api import TimeoutError as PlaywrightTimeout
from portals.base import BasePortal
from core.bob_report import BOBReport
from core.benefit_parser import build_benefit

# Procedure codes we always look for
TARGET_CODES = ["D0120", "D1110", "D1120", "D1206", "D1208", "D1260", "D2740", "D4910"]


class UnitedConcordiaPortal(BasePortal):

    PORTAL_NAME = "United Concordia"
    PORTAL_URL = "https://www.unitedconcordia.com/dental-insurance/providers/"

    async def login(self, credentials: dict) -> None:
        await self._page.goto(self.PORTAL_URL)
        await self._page.get_by_role("link", name=re.compile("provider login", re.I)).click()
        await self._page.get_by_label("User ID").fill(credentials["username"])
        await self._page.get_by_label("Password").fill(credentials["password"])
        await self._page.get_by_role("button", name=re.compile("log in|sign in", re.I)).click()

        # Wait for dashboard — adjust selector to match actual post-login element
        try:
            await self._page.wait_for_selector("[data-testid='dashboard'], .provider-dashboard", timeout=15000)
        except PlaywrightTimeout:
            raise RuntimeError("Login failed or portal layout changed — needs human review")

    async def navigate_to_eligibility(self, patient: dict) -> None:
        # Navigate to eligibility check — selectors must be validated against live portal
        await self._page.get_by_role("link", name=re.compile("eligibility|benefits", re.I)).first.click()
        await self._page.wait_for_load_state("networkidle")

        # Fill patient search form
        await self._page.get_by_label(re.compile("member id|subscriber id", re.I)).fill(patient["subscriber_id"])
        await self._page.get_by_label(re.compile("date of birth", re.I)).fill(patient["dob"])  # MM/DD/YYYY
        await self._page.get_by_role("button", name=re.compile("search|verify", re.I)).click()
        await self._page.wait_for_load_state("networkidle")

    async def extract_bob(self) -> dict:
        """
        Scrape the eligibility results page.
        NOTE: Selectors below are illustrative — validate against the live portal.
        """
        raw = {}

        # Coverage summary block
        summary = self._page.locator(".eligibility-summary, [data-section='coverage']")
        raw["coverage_status"] = await self._safe_text(summary.get_by_text(re.compile("active|inactive", re.I)))
        raw["subscriber_id"]   = await self._safe_text(summary.locator("[data-field='subscriber-id']"))
        raw["group_number"]    = await self._safe_text(summary.locator("[data-field='group-number']"))
        raw["plan_name"]       = await self._safe_text(summary.locator("[data-field='plan-name']"))
        raw["effective_date"]  = await self._safe_text(summary.locator("[data-field='effective-date']"))

        # Financials
        fin = self._page.locator(".deductible-section, [data-section='deductible']")
        raw["annual_max"]          = await self._safe_text(fin.locator("[data-field='annual-max']"))
        raw["deductible_amount"]   = await self._safe_text(fin.locator("[data-field='deductible']"))
        raw["deductible_used"]     = await self._safe_text(fin.locator("[data-field='deductible-used']"))

        # Benefits table — rows keyed by procedure code
        raw["benefits"] = []
        rows = self._page.locator("table.benefits-table tbody tr, [data-section='benefits'] .benefit-row")
        count = await rows.count()
        for i in range(count):
            row = rows.nth(i)
            code      = await self._safe_text(row.locator("[data-col='code'], td:nth-child(1)"))
            desc      = await self._safe_text(row.locator("[data-col='description'], td:nth-child(2)"))
            frequency = await self._safe_text(row.locator("[data-col='frequency'], td:nth-child(3)"))
            last_svc  = await self._safe_text(row.locator("[data-col='last-service'], td:nth-child(4)"))
            if code:
                raw["benefits"].append({
                    "code": code.strip(),
                    "description": desc.strip(),
                    "frequency": frequency.strip(),
                    "last_service": last_svc.strip(),
                })

        return raw

    def build_report(self, raw: dict, patient: dict) -> BOBReport:
        review_reasons = []

        # Parse financials — strip $ and commas
        def parse_money(val: str) -> float | None:
            try:
                return float(re.sub(r"[^\d.]", "", val))
            except (ValueError, TypeError):
                return None

        def parse_date(val: str) -> date | None:
            if not val:
                return None
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
                try:
                    from datetime import datetime
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
            return None

        annual_max  = parse_money(raw.get("annual_max", ""))
        ded_amount  = parse_money(raw.get("deductible_amount", ""))
        ded_used    = parse_money(raw.get("deductible_used", ""))
        ded_remaining = (ded_amount - ded_used) if (ded_amount and ded_used is not None) else None

        # Build benefit lines
        benefits = []
        for b in raw.get("benefits", []):
            last_svc = parse_date(b.get("last_service"))
            benefit = build_benefit(
                procedure_code=b["code"],
                description=b["description"],
                raw_frequency_text=b["frequency"],
                last_service_date=last_svc,
            )
            if benefit.notes:  # AI flagged ambiguity
                review_reasons.append(f"{b['code']}: {benefit.notes}")
            benefits.append(benefit)

        # Flag missing target codes
        found_codes = {b.procedure_code for b in benefits}
        missing = [c for c in TARGET_CODES if c not in found_codes]
        if missing:
            review_reasons.append(f"Target codes not found in portal data: {', '.join(missing)}")

        return BOBReport(
            patient_name=patient.get("name", ""),
            date_of_birth=parse_date(patient.get("dob")),
            subscriber_id=raw.get("subscriber_id", patient.get("subscriber_id", "")),
            member_id=patient.get("member_id"),
            group_number=raw.get("group_number", ""),
            insurance_plan=raw.get("plan_name", ""),
            portal=self.PORTAL_NAME,
            verified_date=date.today(),
            coverage_status=raw.get("coverage_status", "Unknown"),
            coverage_effective_date=parse_date(raw.get("effective_date")),
            coverage_termination_date=None,
            annual_maximum=annual_max,
            deductible_amount=ded_amount,
            deductible_used=ded_used,
            deductible_remaining=ded_remaining,
            benefits=benefits,
            requires_human_review=bool(review_reasons),
            human_review_reasons=review_reasons,
            raw_portal_data=raw,
        )

    async def _safe_text(self, locator) -> str:
        """Return inner text or empty string if element not found."""
        try:
            return await locator.first.inner_text(timeout=3000)
        except Exception:
            return ""
