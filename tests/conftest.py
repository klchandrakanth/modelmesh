import pytest
from modelmesh.providers.base import ChatResponse

@pytest.fixture
def mock_chat_response():
    return ChatResponse(
        model="llama3",
        content="Test response",
        prompt_tokens=5,
        completion_tokens=10,
        id="chatcmpl-test",
    )
