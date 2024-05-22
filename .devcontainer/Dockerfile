FROM nvcr.io/nvidia/pytorch:24.01-py3

ARG DEBIAN_FRONTEND=noninteractive

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin"
