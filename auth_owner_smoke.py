import sys
import os
from fastapi.testclient import TestClient

# Mock data path
STORE_PATH = 'data/openincident_store_owner_smoke.json'
if os.path.exists(STORE_PATH):
    os.remove(STORE_PATH)

# Import app modules
import server.app as appmod
from server.app import app
from server.session_store import InMemorySessionStore

# Rebind session store
new_store = InMemorySessionStore(store_path=STORE_PATH)
appmod.session_store = new_store

client = TestClient(app)

def run_test():
    print("--- Starting Smoke Test ---")
    
    # 1. Register/Login Account A and B
    def reg_and_login(name, email):
        reg_payload = {"name": name, "email": email, "password": "password123"}
        client.post("/auth/register", json=reg_payload)
        login_payload = {"email": email, "password": "password123"}
        resp = client.post("/auth/login", json=login_payload)
        return resp.json()["token"]

    token_a = reg_and_login("User A", "a@example.com")
    token_b = reg_and_login("User B", "b@example.com")
    auth_a = {"Authorization": f"Bearer {token_a}"}
    auth_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Create a project using account A
    proj_payload = {
        "name": "Project A", 
        "repository_url": "https://github.com/example/repo",
        "metadata": {}
    }
    resp = client.post("/projects", json=proj_payload, headers=auth_a)
    assert resp.status_code == 200, f"Create project failed: {resp.text}"
    project = resp.json()
    project_id = project["project_id"]
    print(f"Created project: {project_id}")

    # 3. Verifications
    # a) GET /projects/{id}/summary without auth returns 401
    resp = client.get(f"/projects/{project_id}/summary")
    print(f"a) No auth summary: {resp.status_code}")
    assert resp.status_code == 401

    # b) GET /projects/{id}/summary with account B returns 403
    resp = client.get(f"/projects/{project_id}/summary", headers=auth_b)
    print(f"b) Account B summary: {resp.status_code}")
    assert resp.status_code == 403

    # c) GET /projects/{id}/summary with account A returns 200
    resp = client.get(f"/projects/{project_id}/summary", headers=auth_a)
    print(f"c) Account A summary: {resp.status_code}")
    assert resp.status_code == 200

    # d) GET /projects without auth does not include A-owned project
    resp = client.get("/projects")
    projects_no_auth = resp.json()
    found = any(p["project_id"] == project_id for p in projects_no_auth)
    print(f"d) No auth list includes project: {found}")
    assert not found

    # e) GET /projects with account A includes the project
    resp = client.get("/projects", headers=auth_a)
    projects_a = resp.json()
    found = any(p["project_id"] == project_id for p in projects_a)
    print(f"e) Account A list includes project: {found}")
    assert found

    # f) POST /projects/{id}/stories with account A succeeds
    story_payload = {"stories": [{"title": "Story 1", "description": "Desc"}]}
    resp = client.post(f"/projects/{project_id}/stories", json=story_payload, headers=auth_a)
    print(f"f) Account A post stories: {resp.status_code}")
    assert resp.status_code == 200
    story_id = resp.json()[0]["story_id"]

    # g) POST /stories/{story_id}/analyze with account B returns 403
    resp = client.post(f"/stories/{story_id}/analyze", headers=auth_b)
    print(f"g) Account B analyze story: {resp.status_code}")
    assert resp.status_code == 403

    print("--- SMOKE TEST PASSED ---")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"--- SMOKE TEST FAILED: {e} ---")
        import traceback
        traceback.print_exc()
        sys.exit(1)
