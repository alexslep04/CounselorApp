import pytest
from flask import json
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_start_session(client):
    response = client.post('/start_session', json={'user_id': 'test_user'})
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['message'] == "Session started. What is your name?"

def test_next_step_name(client):
    client.post('/start_session', json={'user_id': 'test_user'})
    response = client.post('/next_step', json={'user_id': 'test_user', 'input': 'John Doe'})
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['message'] == "Please provide your current job description."

# Add more tests for each step and each edge case
