FROM python:3.6.6
LABEL authors="cmc,maus"
RUN apt-get update -y && apt-get install -y postgresql curl
WORKDIR /src/
COPY  requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN useradd -m eastwood
USER eastwood
COPY  ./ .
HEALTHCHECK --interval=60s --timeout=5s \
  CMD  ps -C python3 >/dev/null && echo "OK" || exit 1 
CMD [ "/bin/sh","run.sh" ]
