[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Markdown Support Code for Fair Debate


Current main serve as backend support library for fair-debate-web



## Installation

- clone repo
- `pip install -e .`


## Usage

Convenient helper to get workdir of web app to defined state:

- `fdmd unpack-repos ./content_repos`


Convenient helper to transform plain dir markdown files into a repo with keys:

- `fdmd process-content-dir __FIXTURES_RP__/d00-explanatory-example-debate__plain ./d00-explanatory-example-debate --patches`



# Coding style

We use `black -l 110 ./` to ensure coding style consistency. For commit messages we (now) try to follow the [conventional commits specification](https://www.conventionalcommits.org/en/).
