import pytest
from modelmesh.providers.base import ChatRequest, ChatResponse, Message

def test_chat_request_roundtrip():
    req = ChatRequest(
        model="llama3",
        messages=[Message(role="user", content="Hello")]
    )
    assert req.model == "llama3"
    assert req.messages[0].role == "user"

def test_chat_response_has_required_fields():
    resp = ChatResponse(
        id="resp-1",
        model="llama3",
        content="Hi there",
        prompt_tokens=5,
        completion_tokens=3,
    )
    assert resp.choices[0]["message"]["content"] == "Hi there"
    assert resp.usage["total_tokens"] == 8
