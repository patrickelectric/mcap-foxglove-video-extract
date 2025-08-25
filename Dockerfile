# Use Ubuntu 24.04 as the base image
FROM ubuntu:24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH

# Install Python 3.12, pip, and system dependencies including GStreamer + introspection
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-alsa \
    gstreamer1.0-pulseaudio \
    libgirepository1.0-dev \
    libcairo2-dev \
    pkg-config \
    libglib2.0-dev \
    gcc \
    meson \
    ninja-build \
    curl \
    cmake \
    gir1.2-glib-2.0 \
    gobject-introspection \
    && rm -rf /var/lib/apt/lists/*

# install opencv
RUN apt-get update && apt-get install -y python3-opencv


# Install uv (universal virtualenv/pip replacement)
RUN pip3 install --break-system-packages uv

RUN apt-get update && apt install -y gir1.2-girepository-2.0-dev

# Set working directory
WORKDIR /app

# Copy source code
COPY *.py ./
COPY pyproject.toml ./
COPY uv.lock ./

# Install the project
RUN uv sync --locked

# Set the default command
ENTRYPOINT ["uv", "run", "main.py"]
CMD ["--help"]