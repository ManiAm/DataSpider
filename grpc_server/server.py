#!/usr/bin/env python3

# Author: Mani Amoozadeh
# Email: mani.amoozadeh2@gmail.com

import threading
import grpc
import datetime
import time
import redis
from concurrent import futures
from celery import Celery

import scraper_pb2
import scraper_pb2_grpc

celery_app = Celery(
    "scraper",
    broker="redis://redis_db_spider:6379/0",
    backend="redis://redis_db_spider:6379/0"
)

rds = redis.Redis(host="redis_db_spider", port=6379, db=1)

pending_jobs = set()
pending_jobs_lock = threading.Lock()

def monitor_jobs():

    print("[Monitor] Job monitor thread started", flush=True)

    while True:

        completed = set()

        with pending_jobs_lock:
            job_ids = list(pending_jobs)

        for job_id in job_ids:

            result = celery_app.AsyncResult(job_id)

            if not result.ready():
                continue

            if result.successful():
                on_job_success(job_id, result.result)
            else:
                on_job_failure(job_id, result.result)

            completed.add(job_id)

        # Remove completed jobs
        with pending_jobs_lock:
            pending_jobs.difference_update(completed)

        time.sleep(1)


def on_job_success(job_id, result_data):

    print(f"{datetime.datetime.now().isoformat()} [Callback] Job {job_id} SUCCESS: {result_data}", flush=True)


def on_job_failure(job_id, error):

    print(f"{datetime.datetime.now().isoformat()} [Callback] Job {job_id} FAILED: {error}", flush=True)


class ScraperService(scraper_pb2_grpc.ScraperServiceServicer):

    def SubmitUrl(self, request, context):

        ts = datetime.datetime.now().isoformat()
        url = request.url
        depth = request.depth
        print(f"{ts}: Received SubmitUrl - url={url}, depth={depth}", flush=True)

        job = celery_app.send_task("tasks.start_crawl", args=[url, depth])

        with pending_jobs_lock:
            pending_jobs.add(job.id)

        return scraper_pb2.JobResponse(job_id=job.id)

    def CheckStatus(self, request, context):

        ts = datetime.datetime.now().isoformat()
        job_id = request.job_id
        print(f"{ts}: Received CheckStatus - job_id={job_id}", flush=True)

        result = celery_app.AsyncResult(job_id)
        if not result.ready():
            return scraper_pb2.StatusResponse(status=result.state , content="")

        try:

            meta = result.get()
            batch_id = meta.get("batch_id")

            if rds.exists(f"active_crawl:{batch_id}"):
                return scraper_pb2.StatusResponse(status="IN_PROGRESS", content=f"Crawl still running for batch_id '{batch_id}'")
            else:
                return scraper_pb2.StatusResponse(status="COMPLETE", content=f"Crawl completed for batch_id '{batch_id}'")

        except Exception as e:
            return scraper_pb2.StatusResponse(status="FAILURE", content=f"Task failed: {e}")

def serve():

    print("Starting gRPC server on port 50051...", flush=True)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scraper_pb2_grpc.add_ScraperServiceServicer_to_server(ScraperService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("gRPC server is now running.", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":

    thread_p = threading.Thread(target=monitor_jobs, daemon=True)
    thread_p.start()
    thread_p.join(3)

    serve()
