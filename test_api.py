import requests
try:
    res = requests.post('http://localhost:3000/api/prompts/save_as', json={"content":"test_python", "name":"py_test"}, timeout=5)
    print(f"Status: {res.status_code}")
    print(f"Body: {res.text}")
except Exception as e:
    print(f"Error: {e}")
