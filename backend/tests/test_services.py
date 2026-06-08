import asyncio

from app.config import Settings
from app.deck_generation_service import DeckGenerationService
from app.google_slides_service import GoogleSlidesService
from app.image_store import TemporaryImageStore
from app.models import GeneratedDeck, TableauView
from app.tableau_service import TableauService
from app.token_store import DevelopmentTokenStore


def test_tableau_service_initializes(tmp_path):
    settings = Settings(token_store_path=tmp_path / "tokens.json")
    service = TableauService(settings, DevelopmentTokenStore(settings.token_store_path))

    assert service.get_connection().provider == "tableau"


def test_google_slides_service_initializes(tmp_path):
    settings = Settings(token_store_path=tmp_path / "tokens.json")
    service = GoogleSlidesService(settings, DevelopmentTokenStore(settings.token_store_path))

    assert service.get_connection().provider == "google"


class FakeTableauService:
    async def get_view_lookup(self, view_ids):
        return {view_id: TableauView(id=view_id, workbook_id="workbook-1", name=f"View {view_id}") for view_id in view_ids}

    async def fetch_view_image(self, view_id):
        return f"image-{view_id}".encode()


class FakeGoogleSlidesService:
    def __init__(self):
        self.received_slides = []

    async def create_presentation(self, title, slides):
        self.received_slides = slides
        return GeneratedDeck(
            id="presentation-1",
            title=title,
            url="https://docs.google.com/presentation/d/presentation-1/edit",
            slide_count=len(slides) + 1,
        )


def test_deck_generation_orchestrates_tableau_images_into_google_slides():
    async def run_test():
        google_service = FakeGoogleSlidesService()
        service = DeckGenerationService(
            tableau_service=FakeTableauService(),
            google_slides_service=google_service,
            image_store=TemporaryImageStore(),
            settings=Settings(app_base_url="http://localhost:8000"),
        )

        job = await service.generate(["view-1", "view-2"])

        assert job.status == "completed"
        assert job.generated_deck is not None
        assert job.generated_deck.url == "https://docs.google.com/presentation/d/presentation-1/edit"
        assert [slide["title"] for slide in google_service.received_slides] == ["View view-1", "View view-2"]
        assert all(slide["image_url"].startswith("http://localhost:8000/api/images/") for slide in google_service.received_slides)

    asyncio.run(run_test())
