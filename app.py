import os
import requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# Swiggy's Live Endpoints
SWIGGY_CATALOG_URL = "https://www.swiggy.com/mapi/restaurants/list/update"
SWIGGY_SEND_OTP_URL = "https://www.swiggy.com/dapi/auth/sms-otp"
SWIGGY_VERIFY_OTP_URL = "https://www.swiggy.com/dapi/auth/otp-verify"

def get_proxy_headers(custom_headers=None):
    """Generates standard headers to mimic a real browser request to Swiggy."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.swiggy.com",
        "Referer": "https://www.swiggy.com/",
        "platform": "mweb"
    }
    if custom_headers:
        headers.update(custom_headers)
    return headers

# ----------------- HEALTH & UPTIME ROBOT -----------------
@app.route("/", methods=["GET"])
def home():
    if os.path.exists("index.html"):
        return send_file("index.html")
    return jsonify({"status": "active"}), 200

@app.route("/health", methods=["GET", "HEAD"])
@app.route("/ping", methods=["GET", "HEAD"])
def health_check():
    return jsonify({"status": "healthy", "service": "live-swiggy-proxy"}), 200

# ----------------- PROXY: RESTAURANT CATALOG -----------------
@app.route("/api/proxy/restaurants", methods=["POST"])
def proxy_restaurants():
    """Forwards frontend payload to Swiggy's restaurant list API."""
    client_payload = request.get_json() or {}
    
    try:
        # Forwarding the exact payload received from our HTML to Swiggy
        response = requests.post(
            SWIGGY_CATALOG_URL, 
            json=client_payload, 
            headers=get_proxy_headers(), 
            timeout=15
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({"statusCode": 1, "statusMessage": f"Proxy Error: {str(e)}"}), 502

# ----------------- PROXY: AUTHENTICATION (SEND OTP) -----------------
@app.route("/api/proxy/auth/send-otp", methods=["POST"])
def proxy_send_otp():
    """Forwards mobile number to Swiggy's send-otp endpoint."""
    client_payload = request.get_json() or {}
    mobile = client_payload.get("mobile")

    if not mobile or len(mobile) != 10:
        return jsonify({"statusMessage": "Invalid mobile number"}), 400

    payload = {"mobile": mobile}
    
    try:
        response = requests.post(
            SWIGGY_SEND_OTP_URL, 
            json=payload, 
            headers=get_proxy_headers(), 
            timeout=10
        )
        # Pass Swiggy's exact response back to the HTML frontend
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({"statusMessage": f"Proxy Error: {str(e)}"}), 502

# ----------------- PROXY: AUTHENTICATION (VERIFY OTP) -----------------
@app.route("/api/proxy/auth/verify-otp", methods=["POST"])
def proxy_verify_otp():
    """Forwards OTP and mobile number to Swiggy's verify-otp endpoint."""
    client_payload = request.get_json() or {}
    
    # Swiggy typically requires the OTP and a reference ID (or mobile number depending on the exact API version)
    try:
        response = requests.post(
            SWIGGY_VERIFY_OTP_URL, 
            json=client_payload, 
            headers=get_proxy_headers(), 
            timeout=10
        )
        
        # If verification is successful, Swiggy returns session cookies. 
        # A robust proxy would pass these cookies back to the client.
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({"statusMessage": f"Proxy Error: {str(e)}"}), 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
