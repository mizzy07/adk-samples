import os
import pytest
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from rag.agent import root_agent

async def mock_generate_content_async(*args, **kwargs):
    yield types.GenerateContentResponse.from_dict({'candidates': [{'content': {'parts': [{'text': 'This is a mocked response.'}], 'role': 'model'}}]})

def test_agent_stream(monkeypatch, mocker) -> None:
    """
    Integration test for the agent stream functionality.
    Tests that the agent returns valid streaming responses.
    """
    monkeypatch.setenv("RAG_CORPUS", "projects/mock-project/locations/us-central1/ragCorpora/mock-corpus")
    mocker.patch(
        "google.adk.models.google_llm.GoogleLLM.generate_content_async",
        new=mock_generate_content_async
    )

    session_service = InMemorySessionService()

    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    message = types.Content(
        role="user", parts=[types.Part.from_text(text="Why is the sky blue?")]
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events) > 0, "Expected at least one message"

