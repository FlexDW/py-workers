FROM python:3.12-bullseye
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
COPY . /py-workers
WORKDIR /py-workers
RUN poetry install --no-interaction
