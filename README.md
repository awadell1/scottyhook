# scottyhook

scottyhook is a preposterously blatant clone of [Hooknook], built for
the workflow I've setup for CMU related websites. Namely

1) GitHub Actions for building and testing a Jekyll Website
2) Auto release commit to master and update the `latest` release with built website
3) scottyhook just needs to copy this, to the publishing server

So while [Hooknook], fetches, build and deploys static website. scottyhook just
retrieves the built website and deploys it. Hence it's use is mostly to automate
connecting to a University's VPN.

[Hooknook]:https://github.com/sampsyo/hooknook

## Installation

To install:
```shell
python -m pip install git+https://github.com/awadell1/scottyhook@main
```
