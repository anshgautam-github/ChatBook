"""FastAPI dependency providers.

Centralizing service instantiation here means routes never construct
services directly, which keeps them easy to override in tests.

`get_export_facade` is the only provider routes use — `ExportFacade` is
the one entry point into the export pipeline (see
app/facades/export_facade.py). Nothing under `app/api/` reaches past it
into `ExportService`, `ParserFactory`, or `PDFGenerator` directly.
"""
from app.facades.export_facade import ExportFacade


def get_export_facade() -> ExportFacade:
    return ExportFacade()
