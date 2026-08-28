# Swiggy Express Clone - Live API Integration

A lightweight, responsive food delivery web application that fetches real-time restaurant and menu data directly from Swiggy's live backend APIs. Built with a Python (Flask) backend and a single-file HTML/JS/TailwindCSS frontend.

## 🚀 Features

* **Live Data Fetching:** Uses Python `requests` to securely query Swiggy's live catalog and menu APIs while handling CSRF tokens and session headers to bypass WAF blocks.
* **Dynamic Menu Generation:** Clicks on a restaurant fetch its actual, real-time menu directly from the Swiggy backend.
* **Search & Filter:** Search for restaurants or dishes by name, and filter by "Pure Veg" and "4.0+ Ratings".
* **Cart Management:** Add items to your cart, increase/decrease quantities, and view live total calculations.
* **Checkout Simulation:** Smooth UI flow simulating an order placement and success confirmation.
* **Responsive UI:** Fully responsive design built with Tailwind CSS, mimicking modern food delivery apps.
* **Keep-Alive Ready:** Includes a `/health` endpoint designed specifically for UptimeRobot to prevent Render's free tier from spinning down.

## 🛠️ Tech Stack

* **Backend:** Python 3.11, Flask, Requests, Gunicorn
* **Frontend:** HTML5, Vanilla JavaScript, Tailwind CSS (via CDN), FontAwesome
* **Deployment:** Render (Free Web Service)

## 📁 Project Structure

```text
.
├── app.py              # Flask server handling API requests and serving HTML
├── index.html          # Single-page frontend application
└── requirements.txt    # Python dependencies
