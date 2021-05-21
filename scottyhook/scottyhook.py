import logging
import argparse
from queue import Full
import flask
from flask import Flask
from flask import request
from .worker import Worker


app = Flask(__name__)


@app.before_first_request
def app_setup(app=app):
    """ Set up the app """

    # Create a worker thread.
    if not hasattr(app, "worker"):
        app.worker = Worker(app.config["SCOTTYHOOK_CONFIG"])
        app.worker.start()


@app.route("/", methods=["POST"])
def hook():
    # Dispatch based on event type.
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        return flask.jsonify(status="not a hook"), 403
    elif event_type == "ping":
        return flask.jsonify(status="pong")
    elif event_type == "release":
        return deploy(request.get_json())


def deploy(payload):
    if payload["action"] != "released":
        logging.info("Release is not released -> skipping")
        return flask.jsonify(status="not yet released"), 200

    # Push job to worker
    try:
        app.worker.queue.put(payload, block=False)
        return flask.jsonify(status="will deploy"), 200
    except Full:
        return flask.jsonify(status="deploy queue is full"), 503


def cli(args=None):
    parser = argparse.ArgumentParser("scottyhook")
    parser.add_argument("--config", type=str, default=".scottyhook.yml")
    args = parser.parse_args()

    app.config["SCOTTYHOOK_CONFIG"] = args.config
    app.run()


if __name__ == "__main__":
    cli()
