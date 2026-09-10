# syntax=docker/dockerfile:1

# Match the firmware builder's pinned base while keeping desktop-only packages
# out of the Zephyr image.
FROM ubuntu:24.04@sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea

ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

RUN apt-get update \
	&& apt-get install --yes --no-install-recommends \
		build-essential \
		ca-certificates \
		cmake \
		libgl1-mesa-dev \
		libx11-dev \
		libxcursor-dev \
		libxext-dev \
		libxfixes-dev \
		libxi-dev \
		libxrandr-dev \
		libxss-dev \
		libxtst-dev \
		make \
		ninja-build \
		pkg-config \
		python3 \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace && chown ubuntu:ubuntu /workspace

USER ubuntu
WORKDIR /workspace/app

LABEL org.opencontainers.image.title="Toy Factory host-player build environment"
LABEL org.opencontainers.image.source="https://github.com/aortez/toy-factory"
