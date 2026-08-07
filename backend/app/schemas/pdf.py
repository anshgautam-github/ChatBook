"""API request/response DTOs for PDF generation."""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.conversation import QaSectionDTO


class GeneratePdfRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500, description="Optional document title override")
    source_url: Optional[str] = Field(
        default=None, max_length=2048, description="Original ChatGPT share URL, shown on the cover page if present"
    )
    # Bounded rather than unlimited: this endpoint accepts sections directly
    # from the client with no server-side link back to an actual /parse
    # call, so nothing else stops a request from fabricating an enormous
    # payload — WeasyPrint rendering and (per-section) LaTeX rasterization
    # both cost real CPU time per section, so an unbounded list is a cheap
    # denial-of-service lever. 1000 sections is far beyond any real
    # conversation but well short of "free to send gigabytes."
    selected_sections: List[QaSectionDTO] = Field(
        ..., min_length=1, max_length=1000, description="The Q&A sections the user chose to include, in order"
    )


class GeneratePdfResponse(BaseModel):
    """Reserved for a future async job-based flow.

    The current `/generate-pdf` endpoint streams the PDF directly, so this
    schema isn't used yet but is kept for when generation becomes async.
    """

    job_id: str
    status: str
