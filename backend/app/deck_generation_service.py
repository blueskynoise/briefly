from .config import Settings
from .google_slides_service import GoogleSlidesService
from .image_store import TemporaryImageStore
from .models import DeckGenerationJob
from .tableau_service import TableauService


class DeckGenerationService:
    def __init__(
        self,
        tableau_service: TableauService,
        google_slides_service: GoogleSlidesService,
        image_store: TemporaryImageStore,
        settings: Settings,
    ):
        self.tableau_service = tableau_service
        self.google_slides_service = google_slides_service
        self.image_store = image_store
        self.settings = settings

    async def generate(self, view_ids: list[str]) -> DeckGenerationJob:
        view_lookup = await self.tableau_service.get_view_lookup(view_ids)
        slides: list[dict[str, str]] = []
        for view_id in view_ids:
            image = await self.tableau_service.fetch_view_image(view_id)
            image_id = self.image_store.put(image)
            slides.append(
                {
                    "title": view_lookup[view_id].name,
                    "image_url": f"{self.settings.app_base_url.rstrip('/')}/api/images/{image_id}",
                }
            )
        generated_deck = await self.google_slides_service.create_presentation("Briefly Tableau Export", slides)
        return DeckGenerationJob.create_completed(view_ids=view_ids, generated_deck=generated_deck)
