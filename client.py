from typing import Union, cast
import json
import logging
import subprocess
from enum import IntEnum

logger = logging.getLogger(__name__)


class Network(IntEnum):
    MAINNET = 1
    TESTNET = 1097911063


class CardanoClient:
    _network: Network
    _invalid_hereafter: Union[int, None]

    """interface for using the cardano client without running the actual node"""

    def __init__(self, network: Network):
        self._network = network
        self._invalid_hereafter = None

    def __handle_network(self, cmd) -> list[str]:
        if self._network == Network.TESTNET:
            cmd.extend(
                [
                    "--testnet-magic",
                    str(Network.TESTNET.value),
                ]
            )
        elif self._network == Network.MAINNET:
            cmd.append("--mainnet")
        return cmd

    def create_policy(
        self, verification_key_file: str, signing_key_file: str, policy_script_file: str
    ) -> str:
        # create keys
        cmd = [
            "cardano-cli",
            "address",
            "key-gen",
            "--verification-key-file",
            verification_key_file,
            "--signing-key-file",
            signing_key_file,
        ]
        subprocess.check_output(cmd)

        # fetch time slot
        cmd = self.__handle_network(["bcc", "query", "tip"])
        response = subprocess.check_output(cmd)
        response = subprocess.check_output(["jq", ".slot?"], input=response)
        slot = int(response.decode("utf8").strip()) + 10000
        self._invalid_hereafter = slot

        # calculate key hash
        cmd = [
            "cardano-cli",
            "address",
            "key-hash",
            "--payment-verification-key-file",
            verification_key_file,
        ]
        response = subprocess.check_output(cmd)
        key_hash = response.decode("utf8").strip()

        # create policy script
        with open(policy_script_file, "w") as handle:
            json.dump(
                {
                    "type": "all",
                    "scripts": [
                        {
                            "type": "before",
                            "slot": slot,
                        },
                        {"type": "sig", "keyHash": key_hash},
                    ],
                },
                handle,
            )

        # return policy id
        cmd = [
            "cardano-cli",
            "transaction",
            "policyid",
            "--script-file",
            policy_script_file,
        ]
        response = subprocess.check_output(cmd)
        return response.decode("utf8").strip()

    def query_utxo(self, payment_addr: str) -> list[dict]:
        cmd = self.__handle_network(
            [
                "bcc",
                "query",
                "utxo",
                "--address",
                payment_addr,
                "--json",
            ]
        )
        response = subprocess.check_output(cmd)
        utxo_data = json.loads(response)["utxo"]
        return utxo_data

    def query_protocol_params(self, out_file: str = "protocol.json") -> None:
        cmd = self.__handle_network(
            [
                "bcc",
                "query",
                "protocol-parameters",
                "--out-file",
                out_file,
            ]
        )
        subprocess.check_output(cmd)

    def build_transaction(
        self,
        tx_in: list[str],
        tx_out: list[str],
        out_file: str,
        fee: int = 0,
        nft_string: str = None,
        minting_script_file: str = None,
        metadata_json_file: str = None,
    ) -> None:
        cmd = [
            "cardano-cli",
            "transaction",
            "build-raw",
            "--fee",
            str(fee),
            "--out-file",
            out_file,
        ]
        if self._invalid_hereafter is not None:
            cmd.extend(
                [
                    "--invalid-hereafter",
                    str(self._invalid_hereafter),
                ]
            )
        if nft_string is not None:
            assert minting_script_file is not None, "you must provide a policy script"
            assert metadata_json_file is not None, "you must provide a metadata json"
            cmd.extend(
                [
                    "--mint",
                    nft_string,
                    "--minting-script-file",
                    minting_script_file,
                    "--metadata-json-file",
                    metadata_json_file,
                ]
            )
        for tx in tx_in:
            cmd.extend(["--tx-in", tx])
        for tx in tx_out:
            cmd.extend(["--tx-out", tx])
        subprocess.check_output(cmd)

    def calculate_fee(
        self,
        tx_in: list[str],
        tx_out: list[str],
        tx_body_file: str,
        witness_count: int = 1,
        protocol_params_file: str = "protocol.json",
    ) -> int:
        cmd = self.__handle_network(
            [
                "cardano-cli",
                "transaction",
                "calculate-min-fee",
                "--tx-body-file",
                tx_body_file,
                "--tx-in-count",
                str(len(tx_in)),
                "--tx-out-count",
                str(len(tx_out)),
                "--witness-count",
                str(witness_count),
                "--protocol-params-file",
                protocol_params_file,
            ]
        )
        response = subprocess.check_output(cmd)
        fee = int(response.decode("utf-8").split(" ")[0])
        return fee

    def sign_transaction(
        self, signing_key_files: Union[str, list[str]], tx_body_file: str, out_file: str
    ) -> None:
        if isinstance(signing_key_files, str):
            signing_key_files = [signing_key_files]
        cmd = self.__handle_network(
            [
                "cardano-cli",
                "transaction",
                "sign",
                "--tx-body-file",
                tx_body_file,
                "--out-file",
                out_file,
            ]
        )
        for key in signing_key_files:
            cmd.extend(["--signing-key-file", key])
        subprocess.check_output(cmd)

    def submit_transaction(self, tx_file: str) -> str:
        cmd = self.__handle_network(
            [
                "bcc",
                "transaction",
                "submit",
                "--tx-file",
                tx_file,
            ]
        )
        response = subprocess.check_output(cmd)
        return response.decode("utf-8")
