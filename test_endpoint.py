from app import app
import json

client = app.test_client()
with client.session_transaction() as sess:
    sess['is_admin'] = True

res = client.post('/api/admin/market_control', json={'action': 'open'})
print("STATUS:", res.status_code)
print("BODY:", res.data.decode('utf-8'))
