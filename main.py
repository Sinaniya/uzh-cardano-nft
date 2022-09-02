import time
import logging
import json
import os
from typing import cast
from datetime import datetime
import pandas as pd

from dotenv import load_dotenv

from client import CardanoClient, Network

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# constants
ADA_PER_MINT_UTXO = 3_000_000
ADA_RETURNED = 1_479_280

TX_DRAFT = "distribute.draft"
TX_FINAL = "distribute.final"
TX_SIGNED = "distribute.signed"

POLICY_VKEY = "policy.vkey"
POLICY_SKEY = "policy.skey"
POLICY_SCRIPT = "policy.script"

ASSET_NAME = "UZH BCC: DDiB 22"

# load env variables from .env
logger.info("Loading environment variables")
load_dotenv()
try:
    network = os.environ.get("NETWORK_ID", "testnet").upper()
    network = getattr(Network, network)
except AttributeError:
    logger.error(f"network id {network} is not supported. Aborting process.")
    exit()

payment_addr = None
if network == Network.TESTNET:
    payment_addr = os.environ.get("PAYMENT_ADDR_TESTNET")
elif network == Network.MAINNET:
    payment_addr = os.environ.get("PAYMENT_ADDR_MAINNET")
else:
    raise NotImplementedError(f"network id {network} is not supported")
assert payment_addr is not None, "you must provide the payment address"

payment_skey = os.environ.get("PAYMENT_SKEY")
assert payment_skey is not None, "you must provide the payment signing key file"

# # initialize cardano client
# client = CardanoClient(cast(Network, network))
# policy_id = client.create_policy(
#     POLICY_VKEY,
#     POLICY_SKEY,
#     POLICY_SCRIPT,
# )

path = "data/NFT_mint_namelist_summer_school.csv"
namelist = pd.read_csv(path)
for idx in range(len(namelist)):
    # initialize cardano client
    client = CardanoClient(cast(Network, network))
    policy_id = client.create_policy(
        POLICY_VKEY,
        POLICY_SKEY,
        POLICY_SCRIPT,
    )
    # ==============================
    # step 1
    # ==============================

    # fetch address UTXO
    logger.info("Fetching address UTXOs and available ADA")
    utxo_data = client.query_utxo(payment_addr)

    # calculate available ADA
    total_input_value = 0
    for utxo in utxo_data:
        logger.debug(utxo["tx_hash"])
        for amount in utxo.get("amount", []):
            if amount["unit"] == "lovelace":
                total_input_value += int(amount["quantity"])
    logger.info(f"available ADA: {total_input_value} lovelace")

    # query protocol parameters
    logger.info("Fetching protocol parameters")
    client.query_protocol_params()

    # calculate fees from dummy tx
    logger.info("Calculating fees from a dummy transaction")
    tx_in = ["{}#{}".format(utxo["tx_hash"], utxo["tx_index"]) for utxo in utxo_data]

    # FIXME: hard-coded value
    num_certificates = 1

    tx_out = [
        "{}+{}".format(payment_addr, ADA_PER_MINT_UTXO) for _ in range(num_certificates + 1)
    ]
    client.build_transaction(tx_in, tx_out, TX_DRAFT, fee=0)
    calculated_fee = client.calculate_fee(tx_in, tx_out, TX_DRAFT)
    logger.info(f"fee: {calculated_fee} lovelace")

    # build the actual tx with the correct fee
    logger.info("Building the actual transaction")
    num_ada_needed = num_certificates * ADA_PER_MINT_UTXO
    ada_leftovers = total_input_value - calculated_fee - num_ada_needed
    tx_out = [
        "{}+{}".format(payment_addr, ADA_PER_MINT_UTXO) for _ in range(num_certificates)
    ]
    tx_out.append("{}+{}".format(payment_addr, int(ada_leftovers)))
    client.build_transaction(tx_in, tx_out, "distribute.final", fee=int(calculated_fee))

    # sign the tx
    logger.info("Signing the transaction")
    client.sign_transaction(payment_skey, "distribute.final", "distribute.signed")

    # submit the tx
    logger.info("Submitting the transaction")
    old_utxo = utxo_data
    response = client.submit_transaction("distribute.signed")
    logger.info(response)

    # ==============================
    # step 2
    # ==============================

    while utxo_data == old_utxo:
        # fetch address UTXO
        logger.info("Waiting for the UTXO to be updated...")
        utxo_data = client.query_utxo(payment_addr)
        time.sleep(10)

    # FIXME: hard-coded values
    # recipient = "addr_test1qzy9xh7zgu8f0rljajqqxy62ev24tjv2mdy0ma3ngmx4l636y6ghh98amqfqggj7xh3vlse9r9vw0p6ars4su755dr2syt6r7z"
    # recipient = "addr1qyvx34932vurp4u48vrephw6mjuwzglul86h0xdaqfvm6x7wgejrrtdcgs4whf47cv0ruscfz2gky9ul2truk8h3z8xswv3m73"
    recipient = namelist.loc[idx, "Cardano address1"]

    index = idx

    # ipfs_hash = "QmcmbXqT9B91EKDTbUpBN4QB5U5aBvwPD36WMxAQXnEhnd"
    ipfs_hash = namelist.loc[idx, "IPFSHash"]
    # identity_hash = "6f33e049475dfe1e1c2eb1637e7559ac718ca408e7255d5c920eac2a57124ba5"
    identity_hash = namelist.loc[idx, "IdentityHash"]
    # target_hash = "d0c95e6984132499dadba779ac0aadec393771a24e8d2c749b3206188921ade3"
    target_hash = namelist.loc[idx, "TargetHash"]
    # signature = [
    #     "7e54cac5213639db770c7f51b0122c6a199fe82ff61ffc6860a953ec6ee18f0a",
    #     "3b675c33f1cdc001ba736caaad22175a57b92424469325edc2bcb88a4eda9429",
    # ]
    signature = [
        namelist.loc[idx, "Signature"][:64],
        namelist.loc[idx, "Signature"][64:],
    ]

    asset_name = ASSET_NAME# + str(id)
    asset_name_hex = asset_name.encode("utf-8").hex()

    # filling the Shell metadata
    metadata = {
        "721": {
            policy_id: {
                asset_name: {
                    "name": asset_name,
                    "Program": "Deep Dive into Blockchain 2022",
                    "Institution": "University of Zurich",
                    "image": f"ipfs://{ipfs_hash}",
                    "description": [
                        "https://files.ifi.uzh.ch/bdlt/cert/",
                        "openbadges/courses/2022/course_description.json"
                    ],
                }
            },
            "version": "1.0",
        },
        "1870": {
            "@context": ["https://w3id.org/openbadges/v2;", "https://w3id.org/blockcerts/v2"],
            "id": "https://files.ifi.uzh.ch/bdlt/cert/openbadges/issuer_id.json",
            "type": "Assertion",
            "recipient": [f"{identity_hash}", {
                "type": "IdentityHash",
                "hashed": "true",
            }],
            "issuedOn": f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "badge": ["https://files.ifi.uzh.ch/bdlt/cert/", "openbadges/courses/2022/summerschool_blockchain_id.json"],
            "verification": {
                "type": "signed",
                "creator": "https://files.ifi.uzh.ch/bdlt/cert/openbadges/issuer_id.json",
                "publicKeyOfCreator": [
                    "4cd4a3d6d6b493edd324c3df243342b28efbdaaa4f7c776ab818f84819f08909",
                    "f8c9491994f799465050e1a202a17d13d3b76289150792afbd3b6f4a3439195e",
                ],
                "signature": [*signature, {
                    "type": [
                        "ECDSA",
                        "Extension"
                    ],
                    "targetHash": f"{target_hash}",
                }]
            }
        }
    }
    jsonStr = json.dumps(metadata)
    filename = asset_name + ".json"
    with open(filename, "w", encoding="utf8") as f:
        f.write(jsonStr)

    nft_string = f"1 {policy_id}.{asset_name_hex}"

    # calculate fees from dummy tx
    logger.info("Calculating fees from a dummy transaction")
    utxo = utxo_data[-1]
    ada_leftovers = ADA_PER_MINT_UTXO - ADA_RETURNED
    tx_in = ["{}#{}".format(utxo["tx_hash"], utxo["tx_index"])]
    tx_out = [
        "{}+{}+{}".format(recipient, ADA_RETURNED, nft_string),
        "{}+{}".format(payment_addr, ada_leftovers),
    ]
    tx_body = f"{index}-matx.raw"
    client.build_transaction(
        tx_in,
        tx_out,
        tx_body,
        fee=0,
        nft_string=nft_string,
        minting_script_file=POLICY_SCRIPT,
        metadata_json_file=filename,
    )
    calculated_fee = client.calculate_fee(tx_in, tx_out, tx_body, witness_count=2)
    logger.info(f"fee: {calculated_fee} lovelace")

    # build the actual tx with the correct fee
    logger.info("Building the actual transaction")
    ada_leftovers = ADA_PER_MINT_UTXO - calculated_fee - ADA_RETURNED
    tx_out = [
        "{}+{}+{}".format(recipient, ADA_RETURNED, nft_string),
        "{}+{}".format(payment_addr, ada_leftovers),
    ]
    tx_body = f"{index}-final-matx.raw"
    client.build_transaction(
        tx_in,
        tx_out,
        tx_body,
        fee=calculated_fee,
        nft_string=nft_string,
        minting_script_file=POLICY_SCRIPT,
        metadata_json_file=filename,
    )

    # sign the tx
    logger.info("Signing the transaction")
    tx_signed = f"{index}-matx.signed"
    client.sign_transaction([payment_skey, POLICY_SKEY], tx_body, tx_signed)

    # submit the tx
    logger.info("Submitting the transaction")
    response = client.submit_transaction(tx_signed)
    logger.info(response)

    time.sleep(60)
