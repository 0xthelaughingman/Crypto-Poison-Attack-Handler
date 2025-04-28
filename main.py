import os
from dotenv import load_dotenv
from flipside import Flipside
import pandas as pd
from pandas import DataFrame

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

    query_result_set = flipside.query(query_sql, ttl_minutes=10)

    current_page_number = 1

    # How many records do we want to return in the page?
    page_size = 10000

    # set total pages to 1 higher than the `current_page_number` until
    # we receive the total pages from `get_query_results` given the
    # provided `page_size` (total_pages is dynamically determined by the API
    # based on the `page_size` you provide)
    total_pages = 10

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
        for front_len in range(5, 2, -1):  # front should match a length of 5, 4 or 3 chars minimum...
            for end_len in range(5, 0, -1):  # end should match a minimum of 1 chars...

                # print(key[0:4], from_address[0:4], key[::-1][0:4], from_address[::-1][0:4])
                if key[0:front_len] == from_address[0:front_len] and key[::-1][0:end_len] == from_address[::-1][0:end_len]:
                    score = [front_len, end_len]
                    address_poisoned = key
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


def format_output_dfs(txns_input: DataFrame, poisoners: dict):
    if len(poisoners) == 0:
        return None

    poison_attack_txns = pd.DataFrame(columns=['block_timestamp','block_id','tx_id','index','tx_from','tx_to','amount', 'mint', '__row_index', 'intended_address', 'score'])
    for key, value in poisoners.items():
        df_poision_txns = txns_input[txns_input['tx_from']==key]
        temp_actual_address = [value[2]] * len(df_poision_txns['tx_id'])
        temp_score = [value[3]] * len(df_poision_txns['tx_id'])
        df_poision_txns = df_poision_txns.assign(real_address = temp_actual_address)
        df_poision_txns = df_poision_txns.assign(score = temp_score)
        poison_attack_txns = pd.concat([poison_attack_txns,df_poision_txns])
        # print(poison_attack_txns.to_string())

    victim_txns = pd.DataFrame(columns=['block_timestamp','block_id','tx_id','index','tx_from','tx_to','amount', 'mint', '__row_index', 'intended_address', 'score'])

    for key, value in poisoners.items():
        df_victim_txns = txns_input[txns_input['tx_to'] == key]
        if len(df_victim_txns) != 0: # don't need this check as poison txns always present, but victim may not ever fall for them!
            temp_actual_address = [value[2]] * len(df_poision_txns['tx_id'])
            temp_score = [value[3]] * len(df_poision_txns['tx_id'])
            df_victim_txns = df_victim_txns.assign(real_address=temp_actual_address)
            df_victim_txns = df_victim_txns.assign(score=temp_score)
            victim_txns = pd.concat([victim_txns, df_victim_txns])
            # print(victim_txns.to_string())

    return poison_attack_txns, victim_txns


if __name__ == "__main__":
    #wallet = "37eXkm5EQSVuJBtMxreZs725uPVUNAyzcFZwa7yZzQKM"
    wallet = "5LbwC1ewY3Sca7T8CwzX9wsjvwMAHbdRo6SCQL8j7EWc"
    txns = None
    try:
        txns = get_transactions(wallet)
    except:
        print("Ensure Valid Address/transfer history present.")

    receivers, senders, poisoners = parse_transactions(txns, wallet)
    print(len(receivers), len(senders), len(poisoners))
    if len(poisoners)==0:
        print("No poison attacks detected")
    else:
        poison_attack_txns, victim_txns = format_output_dfs(txns, poisoners)
        print("\nPoison Attack Txns\n" + poison_attack_txns.to_string())

    if len(victim_txns)==0:
        print("Wallet Owner hasn't fallen victim")
    else:
        print("\nVictim Txns:\n" + victim_txns.to_string())

