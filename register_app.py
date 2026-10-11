import urllib.request
import json
import time

BASE_URL = 'https://shiv-database.onrender.com'

def request(method, path, data=None, token=None):
    headers = {'Content-Type': 'application/json', 'User-Agent': 'SHIV-Setup/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{BASE_URL}{path}', headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except:
            return e.code, body

print('1. Checking Render health...')
status, res = request('GET', '/health')
print('Health status:', status, res)

admin_email = 'admin@shreemanglam.com'
admin_user = 'shreemanglam_admin'
admin_pass = 'ShreeManglamSecure2026!'

print('\n2. Registering admin user...')
status, res = request('POST', '/auth/register', {
    'email': admin_email,
    'username': admin_user,
    'password': admin_pass
})
print('Register status:', status, res)

print('\n3. Logging in...')
status, res = request('POST', '/auth/login', {
    'email_or_username': admin_user,
    'password': admin_pass
})
print('Login status:', status, res)

token = None
if isinstance(res, dict) and 'data' in res and 'access_token' in res['data']:
    token = res['data']['access_token']
    print('\nBearer Access Token acquired!')
else:
    print('Failed to acquire token:', res)

if token:
    print('\n4. Creating project: shree-manglam...')
    p_status, p_res = request('POST', '/projects/', {
        'name': 'shree-manglam',
        'description': 'Shree Manglam Luxury Fashion Storefront & Admin Portal',
        'primary_provider': 'shiv_native',
        'fallback_provider': None,
        'auth_provider': 'shiv_native'
    }, token=token)
    print('Project creation status:', p_status, p_res)
    
    project_id = 'shree-manglam'
    if p_status == 200 and 'data' in p_res and 'id' in p_res['data']:
        project_id = p_res['data']['id']
    
    print(f'\n5. Generating API key for project ID: {project_id}...')
    k_status, k_res = request('POST', f'/api-keys/{project_id}?name=shree_manglam_production_key', token=token)
    print('API key status:', k_status, k_res)
    
    if k_status == 200 and 'data' in k_res and 'raw_key' in k_res['data']:
        raw_key = k_res['data']['raw_key']
        print('\n' + '='*60)
        print('SUCCESS! ALL CREDENTIALS CREATED FOR SHREE MANGLAM:')
        print('API Endpoint: ' + BASE_URL)
        print('Project ID:   ' + str(project_id))
        print('API Key:      ' + str(raw_key))
        print('Admin Email:  ' + admin_email)
        print('Admin User:   ' + admin_user)
        print('Admin Pass:   ' + admin_pass)
        print('='*60)
