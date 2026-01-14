import json
import logging
import os
import subprocess
import time
import pytest
import requests
import requests_mock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "http://localhost:8000"
STREAM_URL = f"{BASE_URL}/chat:stream"
HEADERS = {"Content-Type": "application/json", "Accept": "text/event-stream"}


@pytest.fixture(scope="module")
def server_fixture(requests_mock):
    """Fixture to start and stop the server."""
    # Mock the Google AI Platform endpoint to avoid real API calls
    requests_mock.post("https://aiplatform.googleapis.com/v1beta1/projects/adk-devops/locations/global/publishers/google/models/gemini-2.0-flash-001:streamGenerateContent", 
    json={"candidates": [{"content": {"parts": [{"text": "This is a mocked response."}], "role": "model"}}]})


    # Set environment variables for the subprocess
    env = os.environ.copy()
    env["RAG_CORPUS"] = "projects/mock-project/locations/us-central1/ragCorpora/mock-corpus"

    server_process = subprocess.Popen(
        [
            "python",
            "-m",
            "google.adk.cli.adk_web_server",
            "--agent_path=rag.agent",
            "--app_name=rag",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(10)  # Wait for server to start
    yield server_process
    server_process.terminate()


def test_chat_stream(server_fixture: subprocess.Popen[str]) -> None:
    """Test the chat stream functionality."""
    logger.info("Starting chat stream test")

    # Create session first
    user_id = "test_user_123"
    session_data = {"state": {"preferred_language": "English", "visit_count": 1}}

    session_url = f"{BASE_URL}/apps/rag/users/{user_id}/sessions"
    session_response = requests.post(
        session_url,
        headers=HEADERS,
        json=session_data,
        timeout=60,
    )
    assert session_response.status_code == 200
    logger.info(f"Session creation response: {session_response.json()}")
    session_id = session_response.json()["id"]

    # Then send chat message
    data = {
        "app_name": "rag",
        "user_id": user_id,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [{"text": "What's the weather in San Francisco?"}],
        },
        "streaming": True,
    }

    response = requests.post(
        STREAM_URL, headers=HEADERS, json=data, stream=True, timeout=60
    )
    assert response.status_code == 200
    # Parse SSE events from response
    events = []
    for line in response.iter_lines():
        if line:
            # SSE format is "data: {json}"
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                event_json = line_str[6:]  # Remove "data: " prefix
                event = json.loads(event_json)
                events.append(event)
    assert len(events) > 0, "Expected at least one event"


