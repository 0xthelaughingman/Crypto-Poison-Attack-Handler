# Crypto-Poison Attack Handler
A tool that detects and surfaces poison attacks that may have occurred on a given wallet.

## Local Setup / Pre-Requisites
- Python 3 (3.11x recommended)
- A <a href='https://flipsidecrypto.xyz/studio/'>FlipsideCrypto </a> API Key (required for accessing the transactions)

## Local Setup / Configs

- create a `.env` file with the entry `FS_API_KEY=<YOUR_FS_API_KEY>`.
- run `pip install -r requirements.txt` (install all python libs needed)
- run `fastapi dev app.py`
- Finally (if all has gone to plan): open http://127.0.0.1:8000/ 