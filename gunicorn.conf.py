import multiprocessing
import os

# Gunicorn configuration file for Render Deployments

# Bind to the port provided by Render
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Recommended workers for Render Free/Hobby tier (512MB RAM)
# (2 * CPU cores) + 1. Typically 2 or 3 for free tier.
workers = 2

# Type of worker. 'sync' is default. 
# We use threads to allow multiple concurrent requests per worker
# without eating up RAM like multiple processes do.
threads = 4
worker_class = "gthread"

# Timeout for requests (in seconds). 
# Render's load balancer drops connections after 100s anyway.
timeout = 100

# Keepalive for connections
keepalive = 2

# Name of the Gunicorn process
proc_name = "agent_t_t_backend"

# Access log format
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Preload app: load the app code before worker processes are forked.
# This saves RAM but requires databases to be initialized post-fork if using persistent conns.
# In our case we use Turso HTTP so preload is safe and saves RAM.
preload_app = False

# Hook to ensure APScheduler only runs on one worker process
def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
    # We use an environment variable to ensure only ONE worker starts the scheduler
    # This prevents the "duplicate job" and DB locking issues on Render
    if not os.environ.get("SCHEDULER_LOCK"):
        os.environ["SCHEDULER_LOCK"] = "True"
        os.environ["IS_SCHEDULER_WORKER"] = "True"
        server.log.info(f"Worker {worker.pid} designated as Scheduler Worker.")
    else:
        server.log.info(f"Worker {worker.pid} is NOT the scheduler worker.")
