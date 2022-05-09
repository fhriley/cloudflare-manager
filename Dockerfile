ARG BASE_IMAGE="python:3.10-alpine"

FROM $BASE_IMAGE as build

RUN apk add --no-cache git

RUN cd /tmp \
  && git clone --depth=1 https://github.com/fhriley/python-cloudflare.git \
  && cd python-cloudflare \
  && ./setup.py install


FROM $BASE_IMAGE

COPY --from=build /usr/local/lib /usr/local/lib

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY cloudflare_manager ./cloudflare_manager

ENTRYPOINT [ "python", "-m", "cloudflare_manager.main" ]
