AUTOGLOW BACKEND — QUICK START
==============================

1. Install Python 3.10 or newer.
2. Double-click Start_AutoGlow_Backend.bat on Windows.
3. Open http://127.0.0.1:5000.

API ENDPOINTS
- GET    /api/health
- POST   /api/bookings
- GET    /api/bookings
- GET    /api/bookings/<booking_id>
- POST   /api/bookings/<booking_id>/cancel
- PATCH  /api/bookings/<booking_id>/status (requires X-Admin-Key)

The browser frontend uses config.js to locate the backend. Leave API base empty for same-origin local use, or set it to the deployed backend URL for GitHub Pages.

See DEPLOYMENT_STEPS.txt before public deployment. The public deployment still requires the owner's hosting/GitHub authorization.
