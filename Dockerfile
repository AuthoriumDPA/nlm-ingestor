# syntax=docker/dockerfile:experimental
FROM python:3.11-slim-bookworm

# Create a non-root user with numeric UID
RUN groupadd -r appuser -g 1001 && \
    useradd -r -g appuser -u 1001 -m -d /home/appuser appuser

# Update and upgrade system packages to get the latest security fixes
RUN apt-get update && apt-get upgrade -y && \
  apt-get install -y --no-install-recommends libgomp1 wget && \
  rm -rf /var/lib/apt/lists/*

ENV APP_HOME /home/appuser
ENV PYTHONPATH="${PYTHONPATH}:${APP_HOME}"
ENV PYTHONUNBUFFERED=1
# Update system packages to get latest security fixes
RUN apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y --no-install-recommends \
  libxml2 \
  sqlite3 \
  libopenjp2-7 \
  postgresql-client && \
  rm -rf /var/lib/apt/lists/*

# install Java
RUN mkdir -p /usr/share/man/man1 && \
  apt-get update -y && \
  apt-get upgrade -y && \
  apt-get install -y openjdk-17-jre-headless
# install essential packages
RUN apt-get update && apt-get install -y \
  libxml2-dev libxslt-dev zlib1g-dev \
  build-essential libmagic-dev && \
  rm -rf /var/lib/apt/lists/*

# install tesseract and related dependencies
RUN apt-get update && apt-get install -y \
  tesseract-ocr lsb-release && \
  echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" \
  | tee /etc/apt/sources.list.d/notesalexp.list > /dev/null && \
  apt-get update -oAcquire::AllowInsecureRepositories=true && \
  apt-get install -y notesalexp-keyring -oAcquire::AllowInsecureRepositories=true --allow-unauthenticated && \
  apt-get update && \
  apt-get install -y tesseract-ocr libtesseract-dev && \
  wget -P /usr/share/tesseract-ocr/5/tessdata/ \
  https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata && \
  rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y unzip git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}
RUN mkdir -p ${APP_HOME}/whl && chown -R appuser:appuser ${APP_HOME}
COPY whl/*.whl ${APP_HOME}/whl/
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
  poetry config virtualenvs.create false && \
  poetry install --no-root

RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

COPY . ./

# Create .ssh directory and set up SSH known_hosts before switching to non-root user
RUN mkdir -p ${APP_HOME}/.ssh && \
    chmod 700 ${APP_HOME}/.ssh && \
    ssh-keyscan github.com >> ${APP_HOME}/.ssh/known_hosts && \
    chmod 600 ${APP_HOME}/.ssh/known_hosts

# Download NLTK data and tiktoken before switching to non-root user
RUN python -m nltk.downloader -d /usr/share/nltk_data stopwords
RUN python -m nltk.downloader -d /usr/share/nltk_data punkt
RUN python -m nltk.downloader -d /usr/share/nltk_data punkt_tab
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# Set proper ownership for all application files
RUN chown -R appuser:appuser ${APP_HOME}

# Switch to non-root user
USER 1001

RUN chmod +x run.sh

EXPOSE 5001
CMD ./run.sh
