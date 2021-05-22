import logging
import subprocess
import traceback
import threading
import time
from zipfile import ZipFile
from multiprocessing import Process, Queue
from tempfile import TemporaryDirectory, NamedTemporaryFile
import requests


class Worker(Process):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.queue = Queue(maxsize=10)
        self.logger = logging.getLogger("worker")

    def run(self):
        """ Wait for sites to deploy and then deploy them """
        while True:
            try:
                self.handle(self.queue.get())
            except KeyboardInterrupt:
                self.terminate()
            except:
                self.logger.error(
                    "Unable to process request: %s", traceback.format_exc()
                )

    def handle(self, payload):
        """ Handle Release Payloads """
        # Get Release
        if not ("release" in payload and "assets" in payload["release"]):
            self.logger.error("Missing Assets in Payload\n%s", payload)
            raise RuntimeError()

        # Get Repo
        if not ("repository" in payload and "full_name" in payload["repository"]):
            self.logger.error("Missing Repository in Payload\n%s", payload)
            raise RuntimeError()

        # Fetch built Website from GitHub
        repo_name = payload["repository"]["full_name"]
        self.logger.info("received deploy request for %s", repo_name)
        repo_config = self.get_repo_config(repo_name)
        site_dir = fetch_asset(payload["release"]["assets_url"], repo_config["asset"])

        # Deploy Website
        host_target = repo_config["publisher"]
        RcloneThread(site_dir, host_target).start()
        self.logger.info("started rclone for %s", site_dir.name)

    def get_repo_config(self, repo):
        # Load config
        try:
            repo_config = self.config["site"][repo]
        except KeyError:
            logging.error("Missing Config for %s", repo)
            raise

        # Fill in default values
        default_config = {
            "asset": "site-publish.yml",
        }
        for k, v in default_config.items():
            if k not in repo_config:
                repo_config[k] = v

        return repo_config


class RcloneThread(threading.Thread):
    def __init__(self, src: TemporaryDirectory, dst: str):
        super().__init__()
        self.src = src
        self.dst = dst
        self.logger = logging.getLogger("RcloneThread")

    def run(self):
        """ Run rclone in a separate thread """
        start_time = time.monotonic()
        cmd = ["rclone", "-P", "-v", "sync", self.src.name, self.dst]
        self.logger.debug(" ".join(cmd))
        try:
            out = subprocess.run(cmd, shell=True, universal_newlines=True, timeout=900)
        except subprocess.TimeoutExpired:
            # Log exception and return
            self.logger.error(
                "timeout syncing %s: %s", self.src.name, traceback.format_exc()
            )
            self.src.cleanup()
            return

        # Log completion of rclone
        runtime = time.monotonic() - start_time
        if out.returncode == 0:
            self.logger.info(
                "synced %s to %s in %.2f", self.src.name, self.dst, runtime
            )
        else:
            self.logger.error(
                "exited with %d when syncing %s to %s, runtime: %.2f, stdout: %s, stderr:%s",
                out.returncode,
                self.src.name,
                self.dst,
                runtime,
                out.stderr,
                out.stdout,
            )

        # Delete the source directory
        self.src.cleanup()


def fetch_asset(assets_url, asset_name):
    """ Fetch the pre-build website from Github """

    # Get list of assets
    logging.debug("Fetching assets list from %s", assets_url)
    assets = requests.get(assets_url).json()
    logging.debug(assets)
    for item in assets:
        if item["name"] == asset_name:
            asset = item
            break
    if asset is None:
        logging.error("Missing asset: %s", asset_name)
        raise RuntimeError()

    # Download asset
    logging.info("Fetching %s from %s", asset_name, asset["browser_download_url"])
    resp = requests.get(asset["browser_download_url"], allow_redirects=True)
    repo_deployable = TemporaryDirectory()
    with NamedTemporaryFile("wb", delete=False) as repo_zip:
        repo_zip.write(resp.content)
        repo_zip.close()
        ZipFile(repo_zip.name).extractall(path=repo_deployable.name)

    return repo_deployable
