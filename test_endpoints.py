from app import app
import json

client = app.test_client()
with client.session_transaction() as sess:
    sess['is_admin'] = True

for route in ['/api/admin/stats', '/api/admin/leaderboard', '/api/admin/users', '/api/stocks']:
    try:
        res = client.get(route)
        print(f"ROUTE {route} STATUS: {res.status_code}")
        if res.status_code != 200:
            print(res.data)
    except Exception as e:
        print(f"ROUTE {route} FAILED:", e)
