FROM python:3-alpine

# RUN set -eux; \
#     apt-get update; apt-get upgrade -y; \
#     apt-get install -y \
#     mariadb-client \
#     postgresql-client \
#     tzdata; \
#     apt-get clean -y && rm -r /var/lib/apt/lists/*

RUN set -eux; \
    apk --no-cache add \
    mariadb-client \
    postgresql-client \
    tzdata

RUN set -eux; \
    apk add --no-cache --virtual .pynacl_deps build-base python3-dev libffi-dev

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN set -eux; \
    apk del .pynacl_deps

RUN set -eux; \
    mkdir -p /dump

ENV PYTHONUNBUFFERED=1

COPY . ./app/

ENTRYPOINT [ "python3", "/app/main.py" ]