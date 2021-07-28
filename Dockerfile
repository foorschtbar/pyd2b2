FROM python:3-alpine
ENV PYTHONUNBUFFERED=1

# Fix problem with cargo who breaks the GitHub Actions CI/CD pipline
# https://github.com/rust-lang/cargo/issues/9187
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

# Install db clients & requirements for pyAesCrypt (cryptography)
# https://cryptography.io/en/latest/installation.html#rust
# https://stackoverflow.com/questions/46221063/what-is-build-deps-for-apk-add-virtual-command
RUN set -eux \
    && apk update \
    && apk add --no-cache \
    mariadb-client \
    postgresql-client \
    tzdata \
    && apk add --no-cache --update --virtual .build-deps git gcc musl-dev python3-dev libffi-dev openssl-dev cargo \
    && rm -rf /var/cache/apk/*

COPY ./requirements.txt ./

# Install python packages & remove requirements for pyAesCrypt (cryptography) for a smaller image
RUN pip install -U pip \
    && pip install --no-cache-dir -r requirements.txt \
    && set -eux \
    && apk del .build-deps \
    && mkdir -p /dump

COPY . ./app/

ENTRYPOINT [ "python3", "/app/main.py" ]
