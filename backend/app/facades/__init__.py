"""The Facade layer: the single entry point API routes call into.

Routes never import `ExportService`, `ParserFactory`, `ConversationParser`,
or `PDFGenerator` directly — they only ever depend on `ExportFacade` (see
export_facade.py). This is a thin layer whose only job is to be that one
stable entry point; it owns no business rules of its own.
"""
