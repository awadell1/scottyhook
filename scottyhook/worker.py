import logging
import subprocess
import traceback
from zipfile import ZipFile
from multiprocessing import Process, Queue
from tempfile import TemporaryDirectory, NamedTemporaryFile
from subprocess import run
import requests
import yaml

logging.basicConfig(
    filename="worker.log", level=logging.DEBUG,
)
LOGGER = logging.getLogger()


class Worker(Process):
    def __init__(self, config_file):
        super().__init__()
        self.config_file = config_file
        self.queue = Queue(maxsize=10)

    def run(self):
        """ Wait for sites to deploy and then deploy them """
        while True:
            try:
                self.handle(self.queue.get())
            except KeyboardInterrupt:
                self.terminate()
            except:
                LOGGER.error("Unable to process request: %s", traceback.format_exc())

    def handle(self, payload):
        """ Handle Release Payloads """
        # Get Release
        if not ("release" in payload and "assets" in payload["release"]):
            logging.error("Missing Assets in Payload\n%s", payload)
            raise RuntimeError()

        # Get Repo
        if not ("repository" in payload and "full_name" in payload["repository"]):
            logging.error("Missing Repository in Payload\n%s", payload)
            raise RuntimeError()

        # Fetch built Website from GitHub
        repo_name = payload["repository"]["full_name"]
        logging.info("Got Deploy Request for %s", repo_name)
        repo_config = self.get_repo_config(repo_name)
        site_dir = fetch_asset(payload["release"]["assets"], repo_config["asset"])

        # Deploy Website
        host_target = repo_config["publisher"]
        cmd = ["rclone", "-P", "sync", "site_dir", host_target]
        out = subprocess.run(cmd, text=True, capture_output=True)
        LOGGER.info(
            "rclone (%d), stdout: %s, stderr: %s",
            out.returncode,
            out.stdout,
            out.stderr,
        )
        site_dir.cleanup()

    def get_repo_config(self, repo):
        # Load config
        with open(self.config_file, "r") as io:
            repo_config = yaml.safe_load(io)[repo]

        # Fill in default values
        default_config = {
            "asset": "site-publish.yml",
        }
        for k, v in default_config.items():
            if k not in repo_config:
                repo_config[k] = v

        return repo_config


def fetch_asset(assets, asset_name):
    """ Fetch the pre-build website from Github """
    asset = None
    for item in assets:
        if item["name"] == asset_name:
            asset = item
            break
    if asset is None:
        logging.error("Missing asset: %s", asset_name)
        raise RuntimeError()

    # Download asset
    LOGGER.info("Fetching %s from %s", asset_name, asset["browser_download_url"])
    resp = requests.get(asset["browser_download_url"], allow_redirects=True)
    repo_deployable = TemporaryDirectory()
    with NamedTemporaryFile("wb") as repo_zip:
        repo_zip.write(resp.content)
        repo_zip.flush()
        repo_zip.seek(0)
        ZipFile(repo_zip.name).extractall(path=repo_deployable.name)

    return repo_deployable
