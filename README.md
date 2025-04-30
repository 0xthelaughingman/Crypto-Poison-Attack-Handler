# Crypto-Poison Attack Handler
A tool that detects and surfaces poison attacks that may have occurred on a given wallet.

## Deployed Demo
- The deployed demo is available at: https://crypto-poison-attack-handler.onrender.com/


## Local Setup / Pre-Requisites
- Python 3 (3.11x recommended)
- A <a href='https://flipsidecrypto.xyz/studio/'>FlipsideCrypto </a> API Key (required for accessing the transactions)

## Local Setup / Configs

- create a `.env` file with the entry `FS_API_KEY=<YOUR_FS_API_KEY>`.
- run `pip install -r requirements.txt` (install all python libs needed)
- run `fastapi dev app.py`
- Finally (if all has gone to plan): open http://127.0.0.1:8000/ 

## Limits/Truncations:
- The current iteration of the API only looks back

## For Sampling/Methodology
- Refer to:
  - https://flipsidecrypto.xyz/TheLaughingMan/solana---dust-poison-tu4UZz
  - https://fxtwitter.com/LeLaughingMan/status/1917712924379845003
- API Dectection Minimum Poison Scores:
  - Currently for a transaction/wallet to be tagged as a poison txn/poisoner wallet the minimum poison score threshold is `[3,1]`
  - `[3,1]` - with `3` being the minimum matching chars from the start of the address and `1` being the min. number of chars matched from the end of the address to that of a similar receiver of a given wallet.
