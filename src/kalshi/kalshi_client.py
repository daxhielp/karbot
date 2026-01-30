import requests
from requests.exceptions import HTTPError
import base64
import time
from typing import Optional

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class KalshiClient:
    """
    Wrapper class for the KalshiClient class from Kalshi.
    their implementation so buns ts pmo 💔😭
    """
    def __init__(self, key_id: str, key_path: str, env: str = "demo"):
        self.key_id = key_id
        self.key_path = key_path
        self.env = env
        self.client = None

        if not key_id or not key_path:
            print("Could not find valid api keys.")
            return



        # load api key
        print("Loading api key file...")
        try:
            with open(self.key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
                print("Successfully loaded Kalshi key!")
        except FileNotFoundError:
            raise FileNotFoundError("Private key file not found")
        except Exception as e:
            print(f"Ran into unknown error while loading private key file: {e}")
        

        # set api path
        if env == "prod":
            self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        elif env == "demo":
            self.base_url = "https://demo-api.kalshi.co/trade-api/v2"
        else:
            raise ValueError("Invalid env state selected. Make sure to set client env to either \"prod\" or \"demo\".")

        self.session = requests.Session()

        # test api credentials
        try:
            res = self._request("GET", "/account/limits")
            usg_tier = res.get("usage_tier", "N/A")
            print(f"Successfully connected to Kalshi API under {env} environment.")
            print(f"API Usage Tier: {usg_tier}")
        except HTTPError:
            print("Could not verify user. Double check api key id and rsa key file path.")
            return
        except Exception as e:
            print(f"Ran into unexpected error while verifying api credentiials: {e}")
            return

        self.balance = self.get_balance()
        self.read_limit = res.get("read_limit", 20)
        self.write_limit = res.get("write_limit", 20)



    def _request(self, method: str, path: str, params: Optional[dict]=None, json_data: Optional[dict]=None) -> dict:
        """
        Private method to create an http request of given method
        
        :param method: "GET", "POST" "PUT", or "DELETE"
        :type method: str
        :param path: path of desired endpoint e.g. "/balance"
        :type path: str
        :param params: optional request params (relative to endpoint specs)
        :type params: Optional[dict]
        :param json_data: data to send in request (usually for POST methods)
        :type json_data: Optional[dict]
        :return: json response in a dict
        :rtype: dict

        :raise: HTTPError if request/respone failed
        """

        url = self.base_url + path

        # create request object to get formatted path w/params
        req = requests.Request(method, url, params=params, json=json_data)
        prepped = self.session.prepare_request(req)

        # convert time to ms for proper header formatting
        timestamp = str(int(time.time() * 1000))
        signature = self._sign(timestamp, method, prepped.path_url)

        # arrange headers
        headers = {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
        prepped.headers.update(headers)

        response = self.session.send(prepped)
        response.raise_for_status()

        if response.content:
            return response.json()
        return {}

    def _sign(self, timestamp: str, method: str, path: str) -> str:
        """
        Generate SHA256 RSA signature for request
        """
        msg = timestamp + method + path
        signature = self.private_key.sign(
            msg.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')


    def get_balance(self) -> float:
        res = self._request("GET", "/portfolio/balance")
        balance = res.get("balance")
        return balance / 100

    def get_event(self, ticker: str, with_nested_markets=True) -> dict:
        """
        Docstring for get_event
        
        :param ticker: Kalshi event ticker
        :type ticker: str
        :param with_nested_markets: include nested event markets
        :return: response json as a dictionary
        :rtype: dict
        """
        params = {"with_nested_markets": with_nested_markets}
        res = self._request("GET", "/events/"+ticker, params=params)
        return res

    def get_events(self, limit: int=50, **params) -> dict:
        """
        Gets a batch of events specified by the limit.
        
        :param limit: Desired number of events
        :type limit: int
        :param params: Optional params
        :return: A dictionary with all events
        :rtype: dict
        """

        static_param = "?limit=" + str(limit) + "&with_nested_markets=true"
        res = self._request("GET", "/events"+static_param, params=params)
        return res
