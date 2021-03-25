FROM python:3-alpine

# Fix problem with cargo who breaks the GitHub Actions CI/CD pipline
# https://github.com/rust-lang/cargo/issues/9187
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true


# Install db clients
RUN set -eux; \
    apk --no-cache add \
    mariadb-client \
    postgresql-client \
    tzdata

# Install requirements for pyAesCrypt (cryptography)
# https://cryptography.io/en/latest/installation.html#rust
# https://stackoverflow.com/questions/46221063/what-is-build-deps-for-apk-add-virtual-command
RUN set -eux; \
    apk add --no-cache --virtual .build-deps git gcc musl-dev python3-dev libffi-dev openssl-dev cargo

COPY ./requirements.txt ./

RUN pip install -U pip; \
    pip install --no-cache-dir -r requirements.txt

# Remove requirements for pyAesCrypt (cryptography) for a smaller image
RUN set -eux; \
    apk del .build-deps

RUN set -eux; \
    mkdir -p /dump

ENV PYTHONUNBUFFERED=1

COPY . ./app/

ENTRYPOINT [ "python3", "/app/main.py" ]