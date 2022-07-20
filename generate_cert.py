import json
import subprocess
import time

import mysql.connector

mysql_host = "IP_OF_MY_MYSQL_SERVER"
mysql_user = "MY_MYSQL_USERNAME"
mysql_password = "MY_MYSQL_PASSWORD!"
mysql_db = "uzhdemo"
network = "testnet"  # testnet or mainnet - this defines the network-magic when generating transactions and sumbitting them
central_wallet = "addr_test1qpm4flczzpc9l9plkpdckvw2zdyvw789hvjz58lnhx2hunnq4m8r4f8yhh68q5d7lv09rza3cse9y2rdfzdqsr55fz7qj03ju8"  # this is the central wallet where all transactions / NFT's are sent when there is no recipient address defined
ada_per_mint_utxo = 3000000
policy_id = "3d382dd04f6c206e796a1087091d28a404f52d572f246ab566c92c9e"  # my policy_id which is used for minting the NFT's - https://developers.cardano.org/docs/native-tokens/minting-nfts/
ipfs_hash = "QmezezZAQqsx4kE37sgYfkJji9fn1Vq1oJPHtMaGZQvx1y"  # my IPFS hash which points to a static PNG image stored on IPFS - https://bafybeihxo5q5t5l6547lehmv3gtvvi7rmkqcsatbr4jotyikmjlo4vdx5q.ipfs.dweb.link/
central_asset_name = "DEMOCERT"  # name of the NFT's
policy_name = "certdemo"  # name of the NFT's


# Create a continous loop
# This script consists out of 2 steps:
# 1. prepare UTXO's for parallalism, it creates exactly enough outputs to process all certificates which are in queue (max 20 per run)
# 2. consume the previously created UTXO's, 1 for each certificate, this is done

# This is done in 2 steps with the idea in mind that this is a service which will be running constantly
# This way the script will:
# - keep combining old (small) outputs of previous transactions into new outputs (1 per certificat which needs to be processed)
# - able to process all queued certificates in parallel since the script will not have to wait for transactions to settle / be processed by the chain since you are using 1 unique ouput per minting transaction. This creates the notion of parallism.
# Since you will probably be doing a single execution, this Step 1 might not be necessary.
# Depending on if you actually mint the NFT's or just store some metadata on chain, you could even combine multiple metadata entries (like 5 certificates per transaction), the only limit here would be the transaction size limit.

# important, this process includes a payment.skey file which is generated from a mnemonic, this step isn't explained/covered in this script but you can read more here: https://github.com/input-output-hk/cardano-addresses


while True:
    try:

        # Create connection to MySQL database
        mysqldb = mysql.connector.connect(
            host=mysql_host, user=mysql_user, password=mysql_password, database=mysql_db
        )
        mysql_cursor = mysqldb.cursor(buffered=True)
        # Query the MYSQL database for which certificates have to be processed
        # this can be replaced with a CSV file as a source for feeding this script
        get_certs_available = "select * from certificates where status = 0 limit 10"
        mysql_cursor.execute(get_certs_available, ())
        certificates = mysql_cursor.fetchall()

        num_certificates = len(certificates)

        print(f"Checking for certificates to process")
        if num_certificates > 0:
            print(f"found {num_certificates} to process")
            # Beginning of Step 1
            # this part is querying the Cardano-cli (on my own cardano-node) for inputs
            # This part can be replaced by querying the Blockfrost API: https://docs.blockfrost.io/#tag/Cardano-Addresses/paths/~1addresses~1{address}~1utxos/get
            cmd_query_utxo = []
            cmd_query_utxo.append("/home/godspeed/.cabal/bin/cardano-cli")
            cmd_query_utxo.append("query")
            cmd_query_utxo.append("utxo")
            cmd_query_utxo.append("--address")
            cmd_query_utxo.append(central_wallet)
            if network == "testnet":
                cmd_query_utxo.append("--testnet-magic")
                cmd_query_utxo.append("1097911063")
            else:
                cmd_query_utxo.append("--mainnet")
            cmd_query_utxo.append("--out-file")
            cmd_query_utxo.append("utxo.json")
            cmd_query_utxo_response = subprocess.check_output(cmd_query_utxo)

            with open("utxo.json") as utxo_data_file:
                utxo_data = json.load(utxo_data_file)

            input_utxos = list(utxo_data.keys())
            total_input_value = 0
            # print(input_utxos)
            # this part calculates the "Total ADA available" in all the inputs
            for input in input_utxos:
                print(input)
                total_input_value += utxo_data[input]["value"]["lovelace"]

            old_utxo = input_utxos[0].split("#")[0]
            # print(f"total_input_value: {total_input_value}")

            num_ada_needed = num_certificates * ada_per_mint_utxo
            # this part will check if we have enough ADA available to process all the work based on the ada_per_mint_utxo - which is set to 3ADA, this consists of 1.48ADA to send to the recipient + minting fee (0.18ADA) + at least 1 ADA to sent back as change to the wallet that mints the NFT
            if total_input_value > num_ada_needed:
                print(
                    f"Have enough ADA to process... {num_ada_needed}/{total_input_value}"
                )

                # this part creates a dummy transaction which will be used to calculate the fee for minting the asset.
                cmd_create_extra_utxos_dummy = []
                cmd_create_extra_utxos_dummy.append(
                    "/home/godspeed/.cabal/bin/cardano-cli"
                )
                cmd_create_extra_utxos_dummy.append("transaction")
                cmd_create_extra_utxos_dummy.append("build-raw")
                cmd_create_extra_utxos_dummy.append("--fee")
                cmd_create_extra_utxos_dummy.append("{}".format(0))
                for input in input_utxos:
                    cmd_create_extra_utxos_dummy.append("--tx-in")
                    cmd_create_extra_utxos_dummy.append("{}".format(input))
                for i in range(0, num_certificates):
                    # print(f"adding {i} output")
                    cmd_create_extra_utxos_dummy.append("--tx-out")
                    cmd_create_extra_utxos_dummy.append(
                        "{}+{}".format(central_wallet, ada_per_mint_utxo)
                    )
                # print(f"adding {i} change output")
                cmd_create_extra_utxos_dummy.append("--tx-out")
                cmd_create_extra_utxos_dummy.append(
                    "{}+{}".format(central_wallet, ada_per_mint_utxo)
                )
                cmd_create_extra_utxos_dummy.append("--out-file")
                cmd_create_extra_utxos_dummy.append("distribute.draft")
                subprocess.check_output(cmd_create_extra_utxos_dummy)

                cmd_calc_fee = []
                # this part calculates the actual fee which is needed for minting the asset
                cmd_calc_fee.append("/home/godspeed/.cabal/bin/cardano-cli")
                cmd_calc_fee.append("transaction")
                cmd_calc_fee.append("calculate-min-fee")
                cmd_calc_fee.append("--tx-body-file")
                cmd_calc_fee.append("distribute.draft")
                cmd_calc_fee.append("--tx-in-count")
                cmd_calc_fee.append("{}".format(len(input_utxos)))
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
                calculated_fee = int(fee.decode("utf-8").split(" ")[0])

                print(f"fee: {calculated_fee}")

                ada_leftovers = total_input_value - calculated_fee - num_ada_needed
                # After calculating the fee you can start building the actual final transaction with the correct fee
                cmd_create_extra_utxos = []
                cmd_create_extra_utxos.append("/home/godspeed/.cabal/bin/cardano-cli")
                cmd_create_extra_utxos.append("transaction")
                cmd_create_extra_utxos.append("build-raw")
                cmd_create_extra_utxos.append("--fee")
                cmd_create_extra_utxos.append("{}".format(calculated_fee))
                for input in input_utxos:
                    cmd_create_extra_utxos.append("--tx-in")
                    cmd_create_extra_utxos.append("{}".format(input))
                for i in range(0, num_certificates):
                    # print(f"adding {i} output")
                    cmd_create_extra_utxos.append("--tx-out")
                    cmd_create_extra_utxos.append(
                        "{}+{}".format(central_wallet, ada_per_mint_utxo)
                    )

                # print(f"adding change output")
                cmd_create_extra_utxos.append("--tx-out")
                cmd_create_extra_utxos.append(
                    "{}+{}".format(central_wallet, ada_leftovers)
                )
                cmd_create_extra_utxos.append("--out-file")
                cmd_create_extra_utxos.append("distribute.final")
                subprocess.check_output(cmd_create_extra_utxos)
                # print(f"created distribute.final")

                # This part is signing the transaction with the payment.skey file
                cmd_sign_distribute = []
                cmd_sign_distribute.append("/home/godspeed/.cabal/bin/cardano-cli")
                cmd_sign_distribute.append("transaction")
                cmd_sign_distribute.append("sign")
                cmd_sign_distribute.append("--signing-key-file")
                cmd_sign_distribute.append("uzh.payment.skey")
                if network == "testnet":
                    cmd_sign_distribute.append("--testnet-magic")
                    cmd_sign_distribute.append("1097911063")
                else:
                    cmd_sign_distribute.append("--mainnet")
                cmd_sign_distribute.append("--tx-body-file")
                cmd_sign_distribute.append("distribute.final")
                cmd_sign_distribute.append("--out-file")
                cmd_sign_distribute.append("distribute.signed")
                subprocess.check_output(cmd_sign_distribute)
                # print(f"created distribute.signed")

                # This part is submitting the actually signed transaction to the network
                # This can be replaced by submitting the transaction to Blockfrost's API: https://docs.blockfrost.io/#tag/Cardano-Transactions/paths/~1tx~1submit/post
                tx_submit = []
                tx_submit.append("/home/godspeed/.cabal/bin/cardano-cli")
                tx_submit.append("transaction")
                tx_submit.append("submit")
                tx_submit.append("--tx-file")
                tx_submit.append("distribute.signed")
                if network == "testnet":
                    tx_submit.append("--testnet-magic")
                    tx_submit.append("1097911063")
                else:
                    tx_submit.append("--mainnet")
                tx_submit_response = subprocess.check_output(tx_submit)
                print(tx_submit_response)

                num_new_outputs = 0
                utxo = old_utxo
                # this part is checkign to see if the new UTXO's are available before starting Step 2. If they are not available the script will sleep for 5 seconds
                while num_new_outputs < num_certificates and utxo == old_utxo:
                    print("Checking if outputs are available... or sleeping 5 seconds")
                    cmd_query_utxo = []
                    cmd_query_utxo.append("/home/godspeed/.cabal/bin/cardano-cli")
                    cmd_query_utxo.append("query")
                    cmd_query_utxo.append("utxo")
                    cmd_query_utxo.append("--address")
                    cmd_query_utxo.append(central_wallet)
                    if network == "testnet":
                        cmd_query_utxo.append("--testnet-magic")
                        cmd_query_utxo.append("1097911063")
                    else:
                        cmd_query_utxo.append("--mainnet")
                    cmd_query_utxo.append("--out-file")
                    cmd_query_utxo.append("utxo2.json")
                    cmd_query_utxo_response = subprocess.check_output(cmd_query_utxo)

                    with open("utxo2.json") as new_utxo_data_file:
                        new_utxo_data = json.load(new_utxo_data_file)

                    new_input_utxos = list(new_utxo_data.keys())
                    num_new_outputs = len(new_input_utxos)
                    total_input_value = 0
                    # print(input_utxos)
                    num_new_outputs = 0
                    for input in new_input_utxos:
                        print(input)
                        if (
                            new_utxo_data[input]["value"]["lovelace"]
                            == ada_per_mint_utxo
                        ):
                            num_new_outputs += 1
                        total_input_value += new_utxo_data[input]["value"]["lovelace"]
                    utxo = new_input_utxos[0].split("#")[0]
                    time.sleep(5)

                print("Outputs are available... ")

                # Beginning of step 2 where we loop over all the queued certificates and mint them 1 by 1 using the inputs we created in Step1.
                for index, cert in enumerate(certificates):
                    print(f"processing {index} of {num_certificates}")
                    id = cert[0]
                    name = cert[1]
                    firstname = cert[2]
                    email = cert[3]
                    diploma = cert[4]
                    recipient = cert[6]

                    # constructing the outer metadata "shell" for both 721 (NFT) label and 1870 (Open Badge) label.
                    metadata = {
                        "721": {policy_id: {}, "version": "1.0"},
                        "1870": {policy_id: {}, "version": "1.0"},
                    }

                    # building the Assetname (with the ID) to make it unique for each NFT asset
                    # encoding it to hex since it's required on chain.
                    asset_name = central_asset_name + str(id)
                    asset_name_hex = asset_name.encode("utf-8").hex()

                    # Filling the Shell metadata with specific metadata for this certificate / NFT
                    metadata["721"][policy_id][asset_name] = {
                        "name": "{} {}".format(central_asset_name, id),
                        "image": "ipfs://" + ipfs_hash,
                        "fullname": "{}, {}".format(name, firstname),
                        "diploma": f"{diploma}",
                    }
                    metadata["1870"][policy_id][asset_name] = {
                        "name": "{} {}".format(central_asset_name, id),
                        "description": "This is the Open Badge version",
                        "image": "ipfs://" + ipfs_hash,
                        "fullname": "{}, {}".format(name, firstname),
                        "diploma": f"{diploma}",
                    }
                    # storing the constructed metadata in a JSON file which is going to be used in the minting transaction
                    jsonStr = json.dumps(metadata)
                    filename = asset_name + ".json"
                    file = open(filename, "w", encoding="utf8")
                    file.write(jsonStr)
                    file.close()

                    # setting to a static ADA value (in lovelaces) which will be appended to the outgoing transaction.
                    ada_returned = 1479280
                    # calculating how much ADA will be sent back to the central wallet, based on the ADA available and the ADA returned
                    ada_leftovers = ada_per_mint_utxo - ada_returned
                    # constructing the "NFT STRING" which is going to be used in the minting & sending the asset to the recipient
                    nft_string = f"1 {policy_id}.{asset_name_hex}"

                    # Creating a dummy transaction before we can calculate the fee
                    cmd_tx_draft = []
                    cmd_tx_draft.append("/home/godspeed/.cabal/bin/cardano-cli")
                    cmd_tx_draft.append("transaction")
                    cmd_tx_draft.append("build-raw")
                    cmd_tx_draft.append("--fee")
                    cmd_tx_draft.append("{}".format(0))
                    cmd_tx_draft.append("--tx-in")
                    cmd_tx_draft.append("{}#{}".format(utxo, index))
                    cmd_tx_draft.append("--tx-out")
                    cmd_tx_draft.append(
                        "{}+{}+{}".format(recipient, ada_returned, nft_string)
                    )
                    cmd_tx_draft.append("--tx-out")
                    cmd_tx_draft.append("{}+{}".format(central_wallet, ada_leftovers))
                    cmd_tx_draft.append("--mint")
                    cmd_tx_draft.append("{}".format(nft_string))
                    cmd_tx_draft.append("--minting-script-file")
                    cmd_tx_draft.append("{}.policy.script".format(policy_name))
                    cmd_tx_draft.append("--metadata-json-file")
                    cmd_tx_draft.append("{}".format(filename))
                    cmd_tx_draft.append("--out-file")
                    cmd_tx_draft.append("{}-matx.raw".format(index))
                    subprocess.check_output(cmd_tx_draft)

                    cmd_calc_fee = []
                    # calculate the fee for the transaction, this is based on protocol paramters
                    # there is a fixed minimum fee and a variable fee which is based on the amount of bytes we store onchain.
                    cmd_calc_fee.append("/home/godspeed/.cabal/bin/cardano-cli")
                    cmd_calc_fee.append("transaction")
                    cmd_calc_fee.append("calculate-min-fee")
                    cmd_calc_fee.append("--tx-body-file")
                    cmd_calc_fee.append("{}-matx.raw".format(index))
                    cmd_calc_fee.append("--tx-in-count")
                    cmd_calc_fee.append("1")
                    cmd_calc_fee.append("--tx-out-count")
                    cmd_calc_fee.append("2")
                    cmd_calc_fee.append("--witness-count")
                    cmd_calc_fee.append("2")
                    if network == "testnet":
                        cmd_calc_fee.append("--testnet-magic")
                        cmd_calc_fee.append("1097911063")
                    else:
                        cmd_calc_fee.append("--mainnet")
                    cmd_calc_fee.append("--protocol-params-file")
                    cmd_calc_fee.append("protocol.json")

                    fee = subprocess.check_output(cmd_calc_fee)
                    calculated_fee = int(fee.decode("utf-8").split(" ")[0])
                    ada_leftovers = ada_per_mint_utxo - calculated_fee - ada_returned

                    # start constructing the final transaction with the correct fees
                    final_tx = []
                    final_tx.append("/home/godspeed/.cabal/bin/cardano-cli")
                    final_tx.append("transaction")
                    final_tx.append("build-raw")
                    final_tx.append("--fee")
                    final_tx.append("{}".format(calculated_fee))
                    final_tx.append("--tx-in")
                    final_tx.append("{}#{}".format(utxo, index))
                    final_tx.append("--tx-out")
                    final_tx.append(
                        "{}+{}+{}".format(recipient, ada_returned, nft_string)
                    )
                    final_tx.append("--tx-out")
                    final_tx.append("{}+{}".format(central_wallet, ada_leftovers))
                    final_tx.append("--mint")
                    final_tx.append("{}".format(nft_string))
                    final_tx.append("--minting-script-file")
                    final_tx.append("{}.policy.script".format(policy_name))
                    final_tx.append("--metadata-json-file")
                    final_tx.append("{}".format(filename))
                    final_tx.append("--out-file")
                    final_tx.append("{}-final-matx.raw".format(index))
                    subprocess.check_output(final_tx)

                    # sign the final transaction with the payment.skey
                    sign_tx = []
                    sign_tx.append("/home/godspeed/.cabal/bin/cardano-cli")
                    sign_tx.append("transaction")
                    sign_tx.append("sign")
                    sign_tx.append("--signing-key-file")
                    sign_tx.append("uzh.payment.skey".format(id))
                    sign_tx.append("--signing-key-file")
                    sign_tx.append("{}.policy.skey".format(policy_name))
                    if network == "testnet":
                        sign_tx.append("--testnet-magic")
                        sign_tx.append("1097911063")
                    else:
                        sign_tx.append("--mainnet")
                    sign_tx.append("--tx-body-file")
                    sign_tx.append("{}-final-matx.raw".format(index))
                    sign_tx.append("--out-file")
                    sign_tx.append("{}-matx.signed".format(index))
                    subprocess.check_output(sign_tx)

                    # submit the signed transaction
                    tx_submit = []
                    tx_submit.append("/home/godspeed/.cabal/bin/cardano-cli")
                    tx_submit.append("transaction")
                    tx_submit.append("submit")
                    tx_submit.append("--tx-file")
                    tx_submit.append("{}-matx.signed".format(index))
                    if network == "testnet":
                        tx_submit.append("--testnet-magic")
                        tx_submit.append("1097911063")
                    else:
                        tx_submit.append("--mainnet")
                    subprocess.check_output(tx_submit)
                    print(f"Sent {asset_name} to {recipient}")

                    # update the status of the MySQL database so that the record will not be processed again.
                    update_certificate_record = (
                        "UPDATE certificates SET status = 1 WHERE ID = {}".format(id)
                    )
                    mysql_cursor.execute(update_certificate_record, ())
                    mysqldb.commit()
            else:
                print("Not enough ADA available to process")
        else:
            print(f"Nothing to process")

        print(f"Sleeping 5 seconds")
        time.sleep(5)
    except Exception as e:
        print(str(e))
        time.sleep(50)
