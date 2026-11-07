# Both stages start from the same Home Assistant Debian base, which ships s6-overlay v3. CI
# overrides BUILD_FROM with the digest for the architecture it is building; those per-arch
# digests live in .github/workflows and a bump must move all of them together. The digest is
# per-architecture, not a multi-arch index: the image is whatever architecture BUILD_FROM names,
# so build natively and pass the matching digest rather than cross-building.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian@sha256:9281ee991c28532ddae10114ac84750f4aca287a496f6e19583f3a750ad5e786
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest

FROM ${UV_IMAGE} AS uv

FROM ${BUILD_FROM} AS build

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# build-essential and git are for lc3py, which has no wheel and is built from the liblc3 source
# tag named in pyproject.toml. They stay in this stage; only /opt leaves it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

# The base image's Python is older than the one this project requires, so a managed one is
# installed under /opt and copied across with the virtual environment that points at it. Both
# must keep these paths in the final image, because the environment's interpreter is a link into
# the managed Python.
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_PYTHON_DOWNLOADS=automatic \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN uv python install 3.14 \
    && uv venv --python 3.14 /opt/venv

WORKDIR /src
COPY pyproject.toml ./
COPY src ./src

RUN uv pip install --python /opt/venv/bin/python --no-cache . \
    && /opt/venv/bin/python -c "import auracast_player, lc3, bumble, serialx, aiosendspin"


FROM ${BUILD_FROM}

LABEL \
    org.opencontainers.image.source="https://github.com/Yagoor/auracast-addon" \
    org.opencontainers.image.licenses="Apache-2.0"

# libstdc++6 is already present in any image with apt, but the LC3 codec links it, so it is named
# rather than inherited. Nothing for sound is installed: the audio leaves over the air, not
# through a sound card.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# The base image sets this too, but the s6-overlay default is to carry on. A failed start has to
# stop the container rather than leave the services to flounder.
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2

# The Supervisor stops an add-on with the grace its `timeout` option asks for and calls a
# container that overruns it a failure. That option defaults to 10s and config.yaml does not set
# it, so the shutdown needs a budget it cannot exceed. The player is given 3s to stop the
# broadcast and release the controller, and this is the cap on the tail after it. Leaving the
# controller half-closed would make the next start fail, so this is deliberately not shorter.
ENV S6_KILL_GRACETIME=3000

COPY --from=build /opt/python /opt/python
COPY --from=build /opt/venv /opt/venv
COPY rootfs/ /

# No ENTRYPOINT or CMD: the base image's /init runs s6, which starts the services in
# rootfs/etc/s6-overlay.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["/usr/bin/container-healthcheck"]
