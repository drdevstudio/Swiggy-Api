import os
import requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

SWIGGY_CATALOG_URL = "https://www.swiggy.com/mapi/restaurants/list/update"
SWIGGY_IMAGE_BASE = "https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_660/"

def get_headers():
    """Headers strictly matching the HAR file to bypass WAF"""
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://www.swiggy.com",
        "Referer": "https://www.swiggy.com/collections/83631?collection_id=83631&search_context=pizza&tags=layout_CCS_Pizza&type=rcv2",
        "platform": "mweb",
        "__fetch_req__": "true",
        "usecache": "true",
        "user-id": "0",
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-platform": '"Android"',
        "sec-ch-ua-mobile": "?1",
        # Including exact cookies from the HAR file to authenticate the session
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

# Added multiple route aliases so both URLs work
@app.route("/api/swiggy/restaurants", methods=["GET", "POST"])
@app.route("/api/restaurants", methods=["GET", "POST"])
def get_restaurants():
    req_data = request.get_json(silent=True) or {}
    
    # Location coordinates from HAR
    lat = req_data.get("lat") or request.args.get("lat", "25.59430")
    lng = req_data.get("lng") or request.args.get("lng", "85.13520")
    collection_id = req_data.get("collection") or request.args.get("collection", "83631")
    tags = req_data.get("tags") or request.args.get("tags", "layout_CCS_Pizza")

    veg_only = request.args.get("veg") == "true" or req_data.get("veg") is True
    rating_4plus = request.args.get("rating") == "true" or req_data.get("rating") is True
    budget_300 = request.args.get("budget") == "true" or req_data.get("budget") is True
    fast_delivery = request.args.get("fast") == "true" or req_data.get("fast") is True
    category_query = (request.args.get("category") or req_data.get("category") or "").strip().lower()

    facets = {}
    if veg_only: facets["isVeg"] = [{"value": "isVegfacetquery1"}]
    if rating_4plus: facets["rating"] = [{"value": "ratingfacetquery1"}]
    if budget_300: facets["costForTwo"] = [{"value": "costForTwofacetquery0"}]
    if fast_delivery: facets["deliveryTime"] = [{"value": "deliveryTimefacetquery0"}]

    # CSRF token must match the session cookies provided in the headers
    swiggy_payload = {
        "lat": lat,
        "lng": lng,
        "collection": collection_id,
        "tags": tags,
        "sortBy": "",
        "filters": "",
        "type": "rcv2",
        "isFiltered": bool(facets),
        "facets": facets,
        "_csrf": "lSfc5ToQuQ7N-VU-UPX4pMNL-pe6SQnsXAgb_V5Y"
    }

    try:
        response = requests.post(
            SWIGGY_CATALOG_URL,
            json=swiggy_payload,
            headers=get_headers(),
            timeout=15
        )
        
        # If Swiggy blocks the request, this will help us debug in Render logs
        if response.status_code != 200:
            print(f"Swiggy blocked request: {response.status_code} - {response.text}")
            
        swiggy_data = response.json()
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to fetch data: {str(e)}"}), 502

    raw_cards = swiggy_data.get("data", {}).get("cards", [])
    restaurants = []

    for card_wrapper in raw_cards:
        card = card_wrapper.get("card", {}).get("card", {})
        info = card.get("info", {})
        if not info:
            continue

        resto_id = info.get("id")
        name = info.get("name")
        cloud_img = info.get("cloudinaryImageId", "")
        img_url = f"{SWIGGY_IMAGE_BASE}{cloud_img}" if cloud_img else "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=500"

        sla = info.get("sla", {})
        delivery_time = sla.get("slaString", "30-40 mins")
        cuisines = info.get("cuisines", [])
        avg_rating = float(info.get("avgRating") or 4.0)
        cost_str = info.get("costForTwo", "₹300 for two")

        primary_category = "Other"
        if cuisines:
            c_lower = cuisines[0].lower()
            if "pizza" in c_lower: primary_category = "pizza"
            elif "burger" in c_lower: primary_category = "burger"
            elif "dessert" in c_lower or "bakery" in c_lower: primary_category = "desserts"
            elif "indian" in c_lower: primary_category = "indian"
            elif "chinese" in c_lower or "asian" in c_lower: primary_category = "chinese"
            else: primary_category = cuisines[0].lower()

        restaurants.append({
            "id": resto_id,
            "name": name,
            "image": img_url,
            "rating": avg_rating,
            "delivery_time": delivery_time,
            "cost_for_two": cost_str,
            "locality": info.get("locality") or info.get("areaName", "Patna"),
            "cuisines": cuisines,
            "category": primary_category,
            "is_veg": veg_only or "Veg" in str(cuisines)
        })

    if category_query and category_query != "all":
        restaurants = [r for r in restaurants if category_query in r["category"] or any(category_query in c.lower() for c in r["cuisines"])]

    return jsonify({
        "success": True,
        "total": len(restaurants),
        "data": restaurants
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
