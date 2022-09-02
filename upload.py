import os
import shutil

from blockfrost import ApiError, BlockFrostIPFS
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ipfs_id = os.environ.get("BLOCKFROST_PROJECT_ID_IPFS")
assert ipfs_id is not None, "must provide the blockfrost project id"

ipfs = BlockFrostIPFS(project_id=ipfs_id)

path = "data/NFT_mint_namelist_summer_school.csv"
namelist = pd.read_csv(path)
namelist['IPFSHash'] = None

for idx in range(len(namelist)):
    try:
        # upload the file
        ipfs_object = ipfs.add(f"data/students/{idx + 1}.png")
        file_hash = ipfs_object.ipfs_hash
        print(file_hash)

        # pin the file
        result = ipfs.pin_object(file_hash, return_type="json")
        namelist.loc[idx, "IPFSHash"] = file_hash

    except ApiError as e:
        print(e)

namelist.to_csv(path)
