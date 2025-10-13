import os
import requests
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

ETSY_CLIENT_ID = os.getenv("ETSY_CLIENT_ID")
ETSY_CLIENT_SECRET = os.getenv("ETSY_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/etsy/callback"

# --- OAuth --- 
def get_authorization_url(state: str):
    params = {
        "response_type": "code", "client_id": ETSY_CLIENT_ID,
        "redirect_uri": REDIRECT_URI, "scope": "email_r listings_w listings_r shops_r",
        "state": state, "code_challenge": "challenge", "code_challenge_method": "S256"
    }
    return f"https://www.etsy.com/oauth/connect?{urllib.parse.urlencode(params)}"

def exchange_code_for_tokens(code: str):
    data = {
        "grant_type": "authorization_code", "client_id": ETSY_CLIENT_ID,
        "client_secret": ETSY_CLIENT_SECRET, "redirect_uri": REDIRECT_URI,
        "code": code, "code_verifier": "challenge"
    }
    response = requests.post("https://api.etsy.com/v3/public/oauth/token", data=data)
    response.raise_for_status()
    return response.json()

# --- API Calls ---
def get_etsy_shop(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}", "x-api-key": ETSY_CLIENT_ID}
    response = requests.get("https://api.etsy.com/v3/application/users/me/shops", headers=headers)
    response.raise_for_status()
    shops = response.json()
    return shops['results'][0] if shops.get('count', 0) > 0 else None

def get_shop_listings(access_token: str, shop_id: int):
    headers = {"Authorization": f"Bearer {access_token}", "x-api-key": ETSY_CLIENT_ID}
    response = requests.get(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/active", headers=headers)
    response.raise_for_status()
    return response.json()

def get_listing(access_token: str, listing_id: int):
    headers = {"Authorization": f"Bearer {access_token}", "x-api-key": ETSY_CLIENT_ID}
    response = requests.get(f"https://api.etsy.com/v3/application/listings/{listing_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def update_listing_description(access_token: str, shop_id: int, listing_id: int, description: str):
    headers = {"Authorization": f"Bearer {access_token}", "x-api-key": ETSY_CLIENT_ID, "Content-Type": "application/json"}
    data = {"description": description}
    response = requests.patch(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{listing_id}", headers=headers, json=data)
    response.raise_for_status()
    return response.json()