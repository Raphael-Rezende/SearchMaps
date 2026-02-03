FROM node:20-bullseye

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    chromium \
    chromium-driver \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip3 install --no-cache-dir -r api/requirements.txt

COPY web/package.json web/package.json
COPY web/package-lock.json web/package-lock.json
RUN npm --prefix web install

COPY . .
RUN npm --prefix web run build

ENV NEXT_PUBLIC_API_BASE_URL=""

EXPOSE 3000

CMD ["bash", "-lc", "uvicorn api.main:app --host 0.0.0.0 --port 8000 & npm --prefix web run start -- -p ${PORT:-3000}"]
