# Build with podman build --pull=never -f tools/Containerfile.builder
#   -t localhost/bincovering-builder:v1 .
# The base is pinned; this image has no third-party runtime dependencies.
FROM docker.io/library/python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
WORKDIR /runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/runtime
COPY src/bincovering /runtime/bincovering
USER 65534:65534
CMD ["python", "-m", "bincovering.builders.worker"]
