# Runs the FastAPI backend as a container, which is what makes WeasyPrint
# reliable on a host like Render: it needs native system libraries (Pango,
# Cairo, GDK-Pixbuf) that a plain "pip install" runtime doesn't guarantee,
# so this Dockerfile installs them explicitly instead of hoping the host
# already has them.
#
# Pinned to -bookworm specifically (rather than the floating "python:3.12-slim"
# tag) so the apt package names below stay correct even after Debian's
# unqualified default moves to a newer release (e.g. Trixie) — that shift is
# exactly what broke the first build: "libgdk-pixbuf2.0-0" is a legacy
# transitional package name that isn't guaranteed to exist once the
# underlying Debian version moves on.
FROM python:3.12-slim-bookworm

# Pango/Cairo/GDK-Pixbuf: required by WeasyPrint to rasterize HTML to PDF.
# libffi-dev + shared-mime-info: WeasyPrint's own documented dependencies.
# fonts-liberation: a metric-compatible fallback so PDFs still render
# readable text even if a requested font isn't installed in the image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime; it isn't known at build time, so it has to
# be read via shell expansion rather than baked into a plain exec-form CMD.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
