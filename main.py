import logging
import os
from decimal import Decimal

from blockfrost import ApiError, ApiUrls, BlockFrostApi
from dotenv import load_dotenv

from constants import ADA_PER_MINT_UTXO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# load env variables from .env
load_dotenv()
logger.info("creating python SDK for the blockfrost api")

project_id = os.environ.get("BLOCKFROST_PROJECT_ID")
assert project_id is not None, "must provide the blockfrost project id"

address = os.environ.get("WALLET_ADDRESS")
assert address is not None, "must provide a wallet address"

network = os.environ.get("NETWORK_ID", "testnet").lower()
if network == "testnet":
    base_url = ApiUrls.testnet.value
elif network == "mainnet":
    base_url = ApiUrls.mainnet.value
else:
    raise NotImplementedError(f"network id {network} is not supported")

# initialize SDK
api = BlockFrostApi(
    project_id=project_id,
    base_url=base_url,
)
try:
    health = api.health(return_type="json")
    logger.info(f"checking API health - {health}")
except ApiError as e:
    logger.error(e)
if not health.get("is_healthy", False):
    logger.error("API is not healthy, aborting process")
    exit()

# fetch address UTXO and available ADA
logger.info("fetching address UTXOs and available ADA")
utxo_data = api.address_utxos(address, return_type="json")
total_input_value = Decimal(0.0)
for input in utxo_data:
    for amount in input["amount"]:
        if amount["unit"] == "lovelace":
            total_input_value += Decimal(amount["quantity"])
logger.info(f"available ADA: {total_input_value} lovelace")

# calculate fees
breakpoint()
