FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim
RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system simulator \
    && useradd --system --gid simulator --home /app simulator
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && python -m pip uninstall --yes pip setuptools wheel \
    && rm -rf /wheels
WORKDIR /app
RUN mkdir /data && chown simulator:simulator /data
USER simulator
VOLUME ["/data"]
EXPOSE 4840
ENV PROCESS_SIMULATOR_ENDPOINT=opc.tcp://127.0.0.1:4840/process-plant-simulator/
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD ["python", "-m", "process_lens_opcua_simulator.healthcheck"]
ENTRYPOINT ["process-plant-simulator"]
CMD ["serve", "--profile", "smoke", "--endpoint", "opc.tcp://0.0.0.0:4840/process-plant-simulator/", "--history-db", "/data/history.sqlite3"]
