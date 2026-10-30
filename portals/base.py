from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Page
from core.bob_report import BOBReport


class BasePortal(ABC):
    """
    All portal scrapers inherit from this.
    Subclasses implement login(), navigate_to_eligibility(), and extract_bob().
    """

    PORTAL_NAME: str = ""
    PORTAL_URL: str = ""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._page: Page | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        context = await self._browser.new_context()
        self._page = await context.new_page()
        return self

    async def __aexit__(self, *_):
        await self._browser.close()
        await self._playwright.stop()

    @abstractmethod
    async def login(self, credentials: dict) -> None:
        """Log in to the portal using provided credentials."""

    @abstractmethod
    async def navigate_to_eligibility(self, patient: dict) -> None:
        """Navigate to the eligibility/benefits section for a patient."""

    @abstractmethod
    async def extract_bob(self) -> dict:
        """Scrape raw benefit data from the current page. Returns raw dict."""

    async def run(self, credentials: dict, patient: dict) -> BOBReport:
        await self.login(credentials)
        await self.navigate_to_eligibility(patient)
        raw = await self.extract_bob()
        return self.build_report(raw, patient)

    @abstractmethod
    def build_report(self, raw: dict, patient: dict) -> BOBReport:
        """Convert raw scraped data into a standardized BOBReport."""
