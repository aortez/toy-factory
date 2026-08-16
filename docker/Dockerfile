# syntax=docker/dockerfile:1

# Ubuntu 24.04, pinned to its multi-architecture OCI manifest.
FROM ubuntu:24.04@sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea

ARG TARGETARCH
ARG ZEPHYR_SDK_VERSION=1.0.1
ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

RUN apt-get update \
	&& apt-get install --yes --no-install-recommends \
		ca-certificates \
		ccache \
		clang-format \
		cmake \
		curl \
		device-tree-compiler \
		file \
		gcc \
		git \
		gperf \
		libmagic1 \
		make \
		ninja-build \
		python3-dev \
		python3-pip \
		python3-venv \
		wget \
		xz-utils \
	&& rm -rf /var/lib/apt/lists/*

COPY docker/requirements.lock /tmp/requirements.lock

RUN python3 -m venv /opt/venv \
	&& /opt/venv/bin/pip install --disable-pip-version-check --no-cache-dir \
		-r /tmp/requirements.lock \
	&& /opt/venv/bin/pip check \
	&& rm /tmp/requirements.lock

RUN case "${TARGETARCH}" in \
		amd64) \
			sdk_arch=x86_64; \
			sdk_sha=ca9bc0ff66fafca1dac9d592a36d953cf16d096a9d09b1c0357f021cf9f6a7eb; \
			toolchain_sha=21b85981cb5a1818d9bc53d82af80f208946ec038b982ff1907287572ed3a634; \
			;; \
		arm64) \
			sdk_arch=aarch64; \
			sdk_sha=d79c5bfc68e679488659bea289a4026e52a64f03338875c8c9c850fff13cee30; \
			toolchain_sha=b9805b691f2f0a8926c92694cae378d05ba07b76abca745e216fcc52753cc4d6; \
			;; \
		*) \
			echo "unsupported container architecture: ${TARGETARCH}" >&2; \
			exit 1; \
			;; \
	esac; \
	sdk_file="zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-${sdk_arch}_minimal.tar.xz"; \
	toolchain_file="toolchain_gnu_linux-${sdk_arch}_arm-zephyr-eabi.tar.xz"; \
	release_url="https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}"; \
	cd /tmp; \
	curl --fail --location --retry 3 --output "${sdk_file}" "${release_url}/${sdk_file}"; \
	curl --fail --location --retry 3 --output "${toolchain_file}" \
		"${release_url}/${toolchain_file}"; \
	echo "${sdk_sha}  ${sdk_file}" | sha256sum --check --strict; \
	echo "${toolchain_sha}  ${toolchain_file}" | sha256sum --check --strict; \
	mkdir -p /opt/toolchains; \
	tar -xf "${sdk_file}" -C /opt/toolchains; \
	mkdir -p "/opt/toolchains/zephyr-sdk-${ZEPHYR_SDK_VERSION}/gnu"; \
	tar -xf "${toolchain_file}" \
		-C "/opt/toolchains/zephyr-sdk-${ZEPHYR_SDK_VERSION}/gnu"; \
	"/opt/toolchains/zephyr-sdk-${ZEPHYR_SDK_VERSION}/setup.sh" -h; \
	rm "${sdk_file}" "${toolchain_file}"

ENV PATH="/opt/venv/bin:${PATH}"
ENV ZEPHYR_TOOLCHAIN_VARIANT=zephyr
ENV ZEPHYR_SDK_INSTALL_DIR="/opt/toolchains/zephyr-sdk-${ZEPHYR_SDK_VERSION}"

# The Ubuntu image's unprivileged user is UID/GID 1000, matching the usual
# Linux desktop account. A fresh named volume inherits this ownership.
RUN mkdir -p /workspace && chown ubuntu:ubuntu /workspace

USER ubuntu
WORKDIR /workspace/app

LABEL org.opencontainers.image.title="Toy Factory Zephyr build environment"
LABEL org.opencontainers.image.source="https://github.com/aortez/toy-factory"
