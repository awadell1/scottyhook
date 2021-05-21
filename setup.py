from setuptools import setup, find_packages

setup(
    name="scottyhook",
    description="Tool for deploying websites to AWPS",
    version="0.0.1",
    author="Alexius Wadell",
    author_email="awadell@gmail.com",
    packages=find_packages(),
    install_requires=["flask", "pyyaml", "requests"],
    entry_points={"console_scripts": ["scottyhook=scottyhook.scottyhook:cli"]},
)
