import os
import requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

SWIGGY_CATALOG_URL = "https://www.swiggy.com/mapi/restaurants/list/update"
SWIGGY_SEND_OTP_URL = "https://www.swiggy.com/dapi/auth/sms-otp"
SWIGGY_VERIFY_OTP_URL = "https://www.swiggy.com/dapi/auth/otp-verify"
SWIGGY_IMAGE_BASE = "https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_660/"

def get_proxy_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://www.swiggy.com",
        "Referer": "https://www.swiggy.com/",
        "platform": "mweb",
        "__fetch_req__": "true",
        "usecache": "true",
        "user-id": "0"
    }

# ----------------- HOME & HEALTH (UPTIME ROBOT) -----------------
@app.route("/", methods=["GET"])
def home():
    if os.path.exists("index.html"):
        return send_file("index.html")
    return jsonify({
        "status": "online",
        "message": "Swiggy Proxy Server is running on Render",
        "available_endpoints": {
            "live_restaurants_json": "/api/swiggy/restaurants",
            "health_check": "/health"
        }
    }), 200

@app.route("/health", methods=["GET", "HEAD"])
@app.route("/ping", methods=["GET", "HEAD"])
def health_check():
    return jsonify({"status": "healthy", "uptime": "active"}), 200

# ----------------- RESTAURANT JSON ENDPOINT (GET & POST) -----------------
@app.route("/api/swiggy/restaurants", methods=["GET", "POST"])
@app.route("/api/proxy/restaurants", methods=["GET", "POST"])
@app.route("/api/restaurants", methods=["GET", "POST"])
def get_restaurants():
    """Fetches real-time restaurant data directly from Swiggy's backend."""
    # Handle GET query params or POST JSON payload
    req_data = request.get_json(silent=True) or {}
    
    lat = req_data.get("lat") or request.args.get("lat", "25.59430")
    lng = req_data.get("lng") or request.args.get("lng", "85.13520")
    collection_id = req_data.get("collection") or request.args.get("collection", "83631")
    tags = req_data.get("tags") or request.args.get("tags", "layout_CCS_Pizza")

    # Filter params
    veg_only = request.args.get("veg") == "true" or req_data.get("veg") is True
    rating_4plus = request.args.get("rating") == "true" or req_data.get("rating") is True
    budget_300 = request.args.get("budget") == "true" or req_data.get("budget") is True
    fast_delivery = request.args.get("fast") == "true" or req_data.get("fast") is True
    search_query = (request.args.get("search") or req_data.get("search") or "").strip().lower()

    facets = {}
    if veg_only:
        facets["isVeg"] = [{"value": "isVegfacetquery1"}]
    if rating_4plus:
        facets["rating"] = [{"value": "ratingfacetquery1"}]
    if budget_300:
        facets["costForTwo"] = [{"value": "costForTwofacetquery0"}]
    if fast_delivery:
        facets["deliveryTime"] = [{"value": "deliveryTimefacetquery0"}]

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
            headers=get_proxy_headers(),
            timeout=15
        )
        swiggy_data = response.json()
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to reach Swiggy: {str(e)}"}), 502

    # Parse and extract presentation cards from Swiggy
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

        # Generate selectable dishes for the product detail/suggestions flow
        dish_names = [f"Special {c.rstrip('s')}" for c in cuisines[:3]] or ["Classic Margherita", "Cheese Stuffed Garlic Bread", "Choco Mousse"]
        sample_dishes = []
        prices = [199, 249, 329, 149]

        for idx, d_name in enumerate(dish_names):
            sample_dishes.append({
                "id": f"{resto_id}-d{idx+1}",
                "name": d_name,
                "price": prices[idx % len(prices)],
                "is_veg": veg_only or (idx % 2 == 0),
                "rating": round(avg_rating + (0.1 if idx == 0 else -0.1), 1),
                "description": f"Artisan recipe prepared with fresh ingredients from {name}.",
                "image": img_url
            })

        restaurants.append({
            "id": resto_id,
            "name": name,
            "image": img_url,
            "rating": avg_rating,
            "delivery_time": delivery_time,
            "cost_for_two": cost_str,
            "locality": info.get("locality") or info.get("areaName", "Patna"),
            "cuisines": cuisines,
            "menu": sample_dishes
        })

    if search_query:
        restaurants = [
            r for r in restaurants
            if search_query in r["name"].lower() or any(search_query in c.lower() for c in r["cuisines"])
        ]

    return jsonify({
        "success": True,
        "source": "live_swiggy_backend",
        "total": len(restaurants),
        "data": restaurants
    }), 200

# ----------------- AUTHENTICATION ENDPOINTS -----------------
@app.route("/api/proxy/auth/send-otp", methods=["POST"])
def proxy_send_otp():
    client_payload = request.get_json(silent=True) or {}
    mobile = client_payload.get("mobile")

    if not mobile or len(str(mobile)) != 10:
        return jsonify({"statusMessage": "Invalid mobile number"}), 400

    try:
        response = requests.post(
            SWIGGY_SEND_OTP_URL,
            json={"mobile": str(mobile)},
            headers=get_proxy_headers(),
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"statusMessage": f"Proxy Error: {str(e)}"}), 502

@app.route("/api/proxy/auth/verify-otp", methods=["POST"])
def proxy_verify_otp():
    client_payload = request.get_json(silent=True) or {}
    try:
        response = requests.post(
            SWIGGY_VERIFY_OTP_URL,
            json=client_payload,
            headers=get_proxy_headers(),
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"statusMessage": f"Proxy Error: {str(e)}"}), 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
