FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim
RUN groupadd --system simulator && useradd --system --gid simulator --home /app simulator
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
WORKDIR /app
RUN mkdir /data && chown simulator:simulator /data
USER simulator
VOLUME ["/data"]
EXPOSE 4840
ENV PROCESS_SIMULATOR_ENDPOINT=opc.tcp://127.0.0.1:4840/process-plant-simulator/
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD ["python", "-m", "process_lens_opcua_simulator.healthcheck"]
ENTRYPOINT ["process-plant-simulator"]
CMD ["serve", "--endpoint", "opc.tcp://0.0.0.0:4840/process-plant-simulator/", "--history-db", "/data/history.sqlite3"]
