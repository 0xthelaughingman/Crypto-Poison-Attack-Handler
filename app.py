from fastapi import FastAPI, HTTPException

import os
from dotenv import load_dotenv
from flipside import Flipside
import pandas as pd
from pandas import DataFrame
import json

from starlette.responses import RedirectResponse
from fastapi.responses import JSONResponse
from fastapi import Response

load_dotenv()
FS_API_KEY = os.getenv("FS_API_KEY")

flipside = Flipside(FS_API_KEY, "https://api-v2.flipsidecrypto.xyz")


def get_transactions(wallet: str):
    query_sql = f"""
    SELECT
      block_timestamp
      , block_id
      , tx_id
      , index
      , tx_from
      , tx_to
      , amount
      , mint 
    from solana.core.fact_transfers
    WHERE 1=1
      AND tx_from = '{wallet}'

    UNION ALL

    SELECT
      block_timestamp
      , block_id
      , tx_id
      , index
      , tx_from
      , tx_to
      , amount
      , mint 
    from solana.core.fact_transfers
    WHERE 1=1
      AND tx_to = '{wallet}'
    ORDER BY BLOCK_ID ASC, INDEX ASC 
    """

    query_result_set = flipside.query(query_sql, ttl_minutes=2)

    current_page_number = 1

    # How many records do we want to return in the page?
    page_size = 10000

    # set total pages to 1 higher than the `current_page_number` until
    # we receive the total pages from `get_query_results` given the
    # provided `page_size` (total_pages is dynamically determined by the API
    # based on the `page_size` you provide)
    total_pages = 20

    # we'll store all the page results in `all_rows`
    all_rows = []

    while current_page_number <= total_pages:
        results = flipside.get_query_results(
            query_result_set.query_id,
            page_number=current_page_number,
            page_size=page_size
        )

        total_pages = results.page.totalPages
        if results.records:
            all_rows = all_rows + results.records

        current_page_number += 1

    df: DataFrame = pd.DataFrame(all_rows)

    return df


def check_poison_score(from_address: str, receivers: dict):
    score = [0, 0]
    address_poisoned = None
    for key in receivers:
        match = 0
        for front_len in range(5, 2, -1):  # front should match a length of 5, 4 or 3 chars minimum...
            for end_len in range(5, 0, -1):  # end should match a minimum of 1 chars...

                if key[0:front_len] == from_address[0:front_len] and key[::-1][0:end_len] == from_address[::-1][0:end_len]:
                    score = [front_len, end_len]
                    address_poisoned = key
                    match = 1
                    break

            if match == 1:
                break

    # print(score, from_address, address_poisoned)

    return score, address_poisoned


def parse_transactions(txns: DataFrame, wallet: str):
    senders = {}
    receivers = {}
    poisoners = {}
    for row in txns.itertuples():

        if row.tx_from == wallet:  # sends
            to_address = row.tx_to
            if len(receivers) == 0:  # init receivers
                receivers[to_address] = [row.tx_id, row.block_timestamp]

            if to_address not in poisoners and to_address not in receivers:
                receivers[to_address] = [row.tx_id, row.block_timestamp]

        if row.tx_to == wallet:  # receipts
            from_address = row.tx_from
            if len(senders) == 0:  # init senders dict
                senders[from_address] = [row.tx_id, row.block_timestamp]

            if from_address not in senders:

                if len(receivers) == 0:
                    senders[from_address] = [row.tx_id, row.block_timestamp]

                elif from_address in receivers:  # is a valid receiver
                    senders[from_address] = [row.tx_id, row.block_timestamp]

                else:

                    score, address_poisoned = check_poison_score(from_address, receivers)

                    if score[0] == 0:
                        senders[from_address] = [row.tx_id, row.block_timestamp]

                    else:
                        if len(poisoners) != 0 and from_address in poisoners:
                            continue
                        else:
                            poisoners[from_address] = [row.tx_id, row.block_timestamp, address_poisoned, score]
    return receivers, senders, poisoners


def format_output_dfs(txs_input: DataFrame, poisoners: dict):
    if len(poisoners) == 0:
        return [], []

    poison_attack_txs = []

    for key, value in poisoners.items():
        df_poison_txs = txs_input[txs_input['tx_from'] == key]
        temp_actual_address = [value[2]] * len(df_poison_txs['tx_id'])
        temp_score = [value[3]] * len(df_poison_txs['tx_id'])
        df_poison_txs = df_poison_txs.assign(real_address=temp_actual_address)
        df_poison_txs = df_poison_txs.assign(poison_score=temp_score)
        # print(df_poison_txs.to_string())
        for index, row in df_poison_txs.iterrows():
            poison_attack_txs.append(row.to_json())

    victim_txs = []

    for key, value in poisoners.items():
        df_victim_txs = txs_input[txs_input['tx_to'] == key]
        if len(df_victim_txs) != 0:  # don't need this check as poison txns always present, but victim may not ever fall for them!
            temp_actual_address = [value[2]] * len(df_victim_txs['tx_id'])
            temp_score = [value[3]] * len(df_victim_txs['tx_id'])
            df_victim_txs = df_victim_txs.assign(real_address=temp_actual_address)
            df_victim_txs = df_victim_txs.assign(poison_score=temp_score)
            # print(df_victim_txs.to_string())
            for index, row in df_victim_txs.iterrows():
                victim_txs.append(row.to_json())

    return poison_attack_txs, victim_txs


def build_json_response(attack_txs: list, victim_txs: list):
    data = {}
    if len(attack_txs) == 0:
        data['poison_attack_count'] = 0

    else:
        data['poison_attack_count'] = len(attack_txs)
        data['poison_attack_txs'] = []
        for item in attack_txs:
            data['poison_attack_txs'].append(json.loads(item))
        if len(victim_txs) == 0:
            data['victim_tx_count'] = 0
        else:
            data['victim_tx_count'] = len(victim_txs)
            data['victim_txs'] = []
            for item in victim_txs:
                data['victim_txs'].append(json.loads(item))

    json_data = json.dumps(data)
    # print(json_data)
    return json_data


from fastapi import FastAPI

app = FastAPI()


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url='/docs')


@app.get("/{wallet}")
def get_poison_stats(wallet: str):
    txs = None
    try:
        txs = get_transactions(wallet)
    except:
        raise HTTPException(status_code=404,
                            detail="Query Error/Transactions not found. Ensure the wallet is valid and has txn activity.")

    receivers, senders, poisoners = parse_transactions(txs, wallet)

    # print(len(receivers), len(senders), len(poisoners))

    poison_attack_txs, victim_txs = format_output_dfs(txs, poisoners)

    json_response = build_json_response(poison_attack_txs, victim_txs)
    # json is already built, Response over JSONResponse...
    return Response(content=json_response,media_type='application/json')
