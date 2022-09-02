import logging
import os
import json
from typing import cast

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

TX_DRAFT = "tx.draft"
TX_FINAL = "tx.final"
TX_SIGNED = "tx.signed"

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

# initialize cardano client
client = CardanoClient(cast(Network, network))

# ==============================
# step 1
# ==============================
# create metadata json
metadata = {
    "1870": {
        "@context": "https://w3id.org/openbadges/v2",
        "id": "https://files.ifi.uzh.ch/bdlt/cert/openbadges/issuer_id.json",
        "type": "Issuer", 
        "name": "University of Zurich, UZH",
        "url": "https://www.blockchain.uzh.ch/",
        "description": "UZH Blockchain Center",
        "issuer": "Prof. Dr. Claudio J. Tessone, Chairman & Academic Director",
        "email" : "claudio.tessone@uzh.ch",
        "publicKey": [
            "4cd4a3d6d6b493edd324c3df243342b28efbdaaa4f7c776ab818f84819f08909",
            "f8c9491994f799465050e1a202a17d13d3b76289150792afbd3b6f4a3439195e",
        ],
        "verification": "SignedBadge"
    }
    # "1870": {
    #     "@context": "https://w3id.org/openbadges/v2",
    #     "id": [
    #         "https://files.ifi.uzh.ch/bdlt/cert/openbadges/",
    #         "courses/2022/summerschool_blockchain_id.json"
    #     ],
    #     "type": "BadgeClass",
    #     "name": [
    #         "UZH Summer School 2022 Deep Dive into Blockchain",
    #         " - Linking Economics, Technology and Law"
    #     ],
    #     "description": [
    #         "This academic certificate is awarded for passing",
    #         " the UZH Deep Dive into Blockchain 2022 Summer School Course."
    #     ],
    #     "image": "ipfs://QmZosBNUPXccntUU5THgBGkmSqwNPxEBupW3J7wrWTsgSm",
    #     "tags": ["blockchain", "uzh blockchain observatory", "cardano", "academic certificate"],
    #     "issuer": "https://files.ifi.uzh.ch/bdlt/cert/openbadges/issuer_id.json",
    # }
}
for k, v in metadata['1870'].items():
    if isinstance(v, str) and len(v.encode('utf-8')) > 64:
        print(k, v)
        raise

jsonStr = json.dumps(metadata)
filename = "metadata.json"
with open(filename, "w", encoding="utf8") as f:
    f.write(jsonStr)

# ==============================
# step 2
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
tx_out = ["{}+{}".format(payment_addr, 0)]
client.build_transaction(tx_in, tx_out, TX_DRAFT, fee=0, metadata_json_file='metadata.json')
calculated_fee = client.calculate_fee(tx_in, tx_out, TX_DRAFT)
logger.info(f"fee: {calculated_fee} lovelace")

# build the actual tx with the correct fee
logger.info("Building the actual transaction")
num_ada_needed = ADA_PER_MINT_UTXO
ada_leftovers =  total_input_value - calculated_fee
tx_out = ["{}+{}".format(payment_addr, int(ada_leftovers))]
client.build_transaction(tx_in, tx_out, TX_FINAL, fee=int(calculated_fee), metadata_json_file='metadata.json')

# sign the tx
logger.info("Signing the transaction")
client.sign_transaction(payment_skey, TX_FINAL, TX_SIGNED)

# submit the tx
logger.info("Submitting the transaction")
response = client.submit_transaction(TX_SIGNED)
logger.info(response)
