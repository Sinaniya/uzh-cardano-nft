import json
import logging
import os
import subprocess
from decimal import Decimal

from dotenv import load_dotenv

# constants
ADA_PER_MINT_UTXO = 3_000_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# load env variables from .env
logger.info("loading environment variables")
load_dotenv()

project_id = os.environ.get("BLOCKFROST_PROJECT_ID")
assert project_id is not None, "must provide the blockfrost project id"

central_wallet = os.environ.get("WALLET_ADDRESS")
assert central_wallet is not None, "must provide a wallet address"

network = os.environ.get("NETWORK_ID", "testnet").lower()
if network == "testnet":
    os.environ["BLOCKFROST_PROJECT_ID_TESTNET"] = project_id
elif network == "mainnet":
    os.environ["BLOCKFROST_PROJECT_ID_MAINNET"] = project_id
else:
    raise NotImplementedError(f"network id {network} is not supported")

# fetch address UTXO and available ADA
logger.info("fetching address UTXOs and available ADA")
cmd_query_utxo = []
cmd_query_utxo.append("bcc")
cmd_query_utxo.append("query")
cmd_query_utxo.append("utxo")
cmd_query_utxo.append("--address")
cmd_query_utxo.append(central_wallet)
if network == "testnet":
    cmd_query_utxo.append("--testnet-magic")
    cmd_query_utxo.append("1097911063")
else:
    cmd_query_utxo.append("--mainnet")
cmd_query_utxo.append("--json")
cmd_query_utxo_response = subprocess.check_output(cmd_query_utxo)
utxo_data = json.loads(cmd_query_utxo_response)["utxo"]

total_input_value = Decimal(0.0)
for utxo in utxo_data:
    logger.debug(utxo["tx_hash"])
    for amount in utxo.get("amount", []):
        if amount["unit"] == "lovelace":
            total_input_value += Decimal(amount["quantity"])
logger.info(f"available ADA: {total_input_value} lovelace")

# query protocol parameters
logger.info("fetching protocol parameters")
cmd_query_protocol_params = []
cmd_query_protocol_params.append("bcc")
cmd_query_protocol_params.append("query")
cmd_query_protocol_params.append("protocol-parameters")
if network == "testnet":
    cmd_query_protocol_params.append("--testnet-magic")
    cmd_query_protocol_params.append("1097911063")
else:
    cmd_query_protocol_params.append("--mainnet")
cmd_query_protocol_params.append("--out-file")
cmd_query_protocol_params.append("protocol.json")
subprocess.check_output(cmd_query_protocol_params)

# calculate fees from dummy tx
cmd_create_extra_utxos_dummy = []
cmd_create_extra_utxos_dummy.append("cardano-cli")
cmd_create_extra_utxos_dummy.append("transaction")
cmd_create_extra_utxos_dummy.append("build-raw")
cmd_create_extra_utxos_dummy.append("--fee")
cmd_create_extra_utxos_dummy.append("{}".format(0))
for utxo in utxo_data:
    cmd_create_extra_utxos_dummy.append("--tx-in")
    cmd_create_extra_utxos_dummy.append(
        "{}#{}".format(utxo["tx_hash"], utxo["tx_index"])
    )

# FIXME
logger.warning("testing with a hard-coded value num_certificates = 1")
num_certificates = 1

for _ in range(num_certificates):
    cmd_create_extra_utxos_dummy.append("--tx-out")
    cmd_create_extra_utxos_dummy.append(
        "{}+{}".format(central_wallet, ADA_PER_MINT_UTXO)
    )
cmd_create_extra_utxos_dummy.append("--tx-out")
cmd_create_extra_utxos_dummy.append("{}+{}".format(central_wallet, ADA_PER_MINT_UTXO))
cmd_create_extra_utxos_dummy.append("--out-file")
cmd_create_extra_utxos_dummy.append("distribute.draft")
subprocess.check_output(cmd_create_extra_utxos_dummy)

cmd_calc_fee = []
cmd_calc_fee.append("cardano-cli")
cmd_calc_fee.append("transaction")
cmd_calc_fee.append("calculate-min-fee")
cmd_calc_fee.append("--tx-body-file")
cmd_calc_fee.append("distribute.draft")
cmd_calc_fee.append("--tx-in-count")
cmd_calc_fee.append("{}".format(len(utxo_data)))
cmd_calc_fee.append("--tx-out-count")
cmd_calc_fee.append(f"{num_certificates+1}")
cmd_calc_fee.append("--witness-count")
cmd_calc_fee.append("1")
if network == "testnet":
    cmd_calc_fee.append("--testnet-magic")
    cmd_calc_fee.append("1097911063")
else:
    cmd_calc_fee.append("--mainnet")
cmd_calc_fee.append("--protocol-params-file")
cmd_calc_fee.append("protocol.json")
fee = subprocess.check_output(cmd_calc_fee)
calculated_fee = Decimal(fee.decode("utf-8").split(" ")[0])

logger.info(f"estimated fee: {calculated_fee} lovelace")
