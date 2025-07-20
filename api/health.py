from fastapi import FastAPI, status, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()


@app.get("/healthz", status_code=status.HTTP_200_OK)
def healthz():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    # check ZMQ sockets and IB connection
    ...


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
