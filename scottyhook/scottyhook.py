import logging
import argparse
import hmac
import hashlib
from queue import Full
import yaml
import flask
from flask import Flask
from flask import request
import netaddr
from .worker import Worker
from .utils import get_with_backoff, setup_logging


app = Flask(__name__)
LOGGER = logging.getLogger("api")


def app_setup(app=app):
    """ Set up the app """

    # Load Config
    with open(app.config["SCOTTYHOOK_CONFIG"], "r") as io:
        app.scottyhook_config = yaml.safe_load(io)

    # Create a worker thread.
    if not hasattr(app, "worker"):
        app.worker = Worker(app.config["SCOTTYHOOK_CONFIG"])
        app.worker.start()

    # Get Whitelist
    whitelist = []
    for ip in app.scottyhook_config["api"]["whitelist"]:
        if ip == "github":
            github_ip = get_with_backoff("https://api.github.com/meta").json()["hooks"]
            whitelist.extend([netaddr.IPNetwork(x) for x in github_ip])
        else:
            whitelist.append(ip)
    app.scottyhook_config["api"]["whitelist"] = whitelist
    LOGGER.debug("API Whitelist: %s", ", ".join([str(ip) for ip in whitelist]))


def verify_client():
    """ Verify client is github or on whitelist """
    addr = request.remote_addr
    for ip in app.scottyhook_config["api"]["whitelist"]:
        if addr in ip:
            return True
    return False


def verify_signature():
    if "secret" not in app.scottyhook_config["api"]:
        LOGGER.debug("api.secret not set -> not validating")
        return True
    secret = app.scottyhook_config["api"]["secret"]

    if "X-Hub-Signature-256" in request.headers:
        server_digest = request.headers["X-Hub-Signature-256"]
        digestmod = hashlib.sha256
    elif "X-Hub-Signature" in request.headers:
        server_digest = request.headers["X-Hub-Signature-256"]
        digestmod = hashlib.sha1
    else:
        LOGGER.debug("missing server digest")
        return False

    # Compute Digest
    our_digest = (
        "sha256="
        + hmac.new(
            secret.encode(),
            digestmod=digestmod,
            msg=request.get_data(as_text=True).encode(),
        ).hexdigest()
    )
    valid = hmac.compare_digest(our_digest, server_digest)
    if not valid:
        LOGGER.debug("server digest: %s, our digest: %s", server_digest, our_digest)
    return valid


@app.route("/", methods=["POST"])
def hook():

    # Check if on whitelist
    LOGGER.debug("Got post at / from %s", request.remote_addr)
    if not verify_client():
        LOGGER.warning("Request from not whitelisted IP: %s", request.remote_addr)
        return flask.jsonify(status="not on whitelist"), 403

    if not verify_signature():
        return flask.jsonify(status="Unauthorized"), 401

    # Dispatch based on event type.
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        return flask.jsonify(status="not a hook"), 403
    elif event_type == "ping":
        return flask.jsonify(status="pong")
    elif event_type == "release":
        return deploy(request.get_json())
    else:
        return flask.jsonify(status="not a hook"), 403


def deploy(payload):
    if payload["action"] != "released":
        LOGGER.info("Release is not released -> skipping")
        return flask.jsonify(status="not yet released"), 200

    # Push job to worker
    try:
        app.worker.queue.put(payload, block=False)
        LOGGER.info("Added to deploy queue")
        return flask.jsonify(status="will deploy"), 200
    except Full:
        LOGGER.error("Deploy queue is full")
        return flask.jsonify(status="deploy queue is full"), 503


def cli(args=None):
    parser = argparse.ArgumentParser("scottyhook")
    parser.add_argument("--config", type=str, default=".scottyhook.yml")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Configure logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logging.info("Log Level: %s", logger.getEffectiveLevel())

    # Configure flask app
    app.config["SCOTTYHOOK_CONFIG"] = args.config
    app_setup(app)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    cli()
