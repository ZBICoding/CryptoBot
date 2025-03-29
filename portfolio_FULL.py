import time
import requests
import urllib.parse
import hashlib
import hmac
import base64

def get_portfolio():
    try:
        with open('kraken.key') as f:
            lines = f.readlines()
        api_key = lines[0].split()[1].strip()
        api_sec = lines[1].split()[1].strip()

        nonce = str(int(time.time() * 1000000))
        uri_path = '/0/private/Balance'
        url = 'https://api.kraken.com' + uri_path
        data = {'nonce': nonce}
        postdata = urllib.parse.urlencode(data)
        encoded = (str(nonce) + postdata).encode()
        message = uri_path.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(api_sec), message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        headers = {
            'API-Key': api_key,
            'API-Sign': sigdigest.decode()
        }

        response = requests.post(url, headers=headers, data=data)
        result = response.json()

        if result.get("error"):
            print("❌ Kraken hiba:", result["error"])
            return {}
        return result["result"]

    except Exception as e:
        print("⚠️ Portfólió lekérési hiba:", e)
        return {}
