import os
import requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

SWIGGY_CATALOG_URL = "https://www.swiggy.com/mapi/restaurants/list/update"
SWIGGY_MENU_URL = "https://www.swiggy.com/mapi/menu/pl"
SWIGGY_IMAGE_BASE = "https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_660/"

def get_headers():
    """Headers required to bypass Swiggy WAF"""
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://www.swiggy.com",
        "Referer": "https://www.swiggy.com/",
        "platform": "mweb",
        "__fetch_req__": "true",
        "usecache": "true",
        "user-id": "0",
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-platform": '"Android"',
        "sec-ch-ua-mobile": "?1",
        "Cookie": "__SW=ufYvJoEWxr_-esm0GbSlnbQV0Eqi7K2S; _device_id=7994edab-837b-de44-d7ef-828df1fc1272; _swuid=7994edab-837b-de44-d7ef-828df1fc1272; _sid=tbbde3ab7fa-08f0-4282-b604-9823578b5; _gcl_au=1.1.1387294068.1787572948"
    }

@app.route("/", methods=["GET"])
def home():
    if os.path.exists("index.html"):
        return send_file("index.html")
    return jsonify({"status": "online"}), 200

@app.route("/health", methods=["GET", "HEAD"])
@app.route("/ping", methods=["GET", "HEAD"])
def health_check():
    return jsonify({"status": "healthy", "uptime": "active"}), 200

@app.route("/api/restaurants", methods=["POST"])
def get_restaurants():
    """Proxies request to Swiggy to get live restaurants"""
    req_data = request.get_json() or {}
    
    try:
        response = requests.post(
            SWIGGY_CATALOG_URL, 
            json=req_data, 
            headers=get_headers(), 
            timeout=15
        )
        swiggy_data = response.json()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 502

    raw_cards = swiggy_data.get("data", {}).get("cards", [])
    restaurants = []

    for card_wrapper in raw_cards:
        card = card_wrapper.get("card", {}).get("card", {})
        info = card.get("info", {})
        if not info: continue

        resto_id = info.get("id")
        name = info.get("name")
        cloud_img = info.get("cloudinaryImageId", "")
        img_url = f"{SWIGGY_IMAGE_BASE}{cloud_img}" if cloud_img else ""

        sla = info.get("sla", {})
        delivery_time = sla.get("slaString", "30-40 mins")
        cuisines = info.get("cuisines", [])
        avg_rating = float(info.get("avgRating") or 4.0)
        cost_str = info.get("costForTwo", "₹300 for two")

        restaurants.append({
            "id": resto_id,
            "name": name,
            "image": img_url,
            "rating": avg_rating,
            "delivery_time": delivery_time,
            "cost_for_two": cost_str,
            "locality": info.get("locality") or info.get("areaName", ""),
            "cuisines": cuisines
        })

    return jsonify({"success": True, "total": len(restaurants), "data": restaurants}), 200

@app.route("/api/menu", methods=["GET"])
def get_menu():
    """Proxies request to Swiggy to get the LIVE menu for a specific restaurant"""
    resto_id = request.args.get("restaurantId")
    lat = request.args.get("lat", "25.59430")
    lng = request.args.get("lng", "85.13520")

    if not resto_id:
        return jsonify({"success": False, "error": "Missing restaurantId"}), 400

    params = {
        "page-type": "REGULAR_MENU",
        "complete-menu": "true",
        "lat": lat,
        "lng": lng,
        "restaurantId": resto_id
    }

    try:
        response = requests.get(SWIGGY_MENU_URL, params=params, headers=get_headers(), timeout=15)
        swiggy_data = response.json()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 502

    # Extract real menu items from Swiggy's nested JSON
    menu_items = []
    raw_cards = swiggy_data.get("data", {}).get("cards", [])
    
    for card_wrapper in raw_cards:
        grouped_card = card_wrapper.get("groupedCard", {}).get("cardGroupMap", {}).get("REGULAR", {}).get("cards", [])
        for group in grouped_card:
            item_cards = group.get("card", {}).get("card", {}).get("itemCards", [])
            for item in item_cards:
                info = item.get("card", {}).get("info", {})
                if info:
                    price = info.get("price") or info.get("defaultPrice") or 0
                    img_id = info.get("imageId", "")
                    
                    # Prevent duplicates
                    if not any(m['id'] == info.get("id") for m in menu_items):
                        menu_items.append({
                            "id": info.get("id"),
                            "name": info.get("name"),
                            "price": price / 100 if price else 0,
                            "desc": info.get("description", ""),
                            "is_veg": info.get("isVeg", 0) == 1,
                            "rating": info.get("ratings", {}).get("aggregatedRating", {}).get("rating", "N/A"),
                            "image": f"{SWIGGY_IMAGE_BASE}{img_id}" if img_id else ""
                        })

    return jsonify({"success": True, "total": len(menu_items), "data": menu_items}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
