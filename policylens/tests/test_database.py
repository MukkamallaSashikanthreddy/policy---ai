from policylens.database import Database


def test_conversation_history_round_trip(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    session_id = db.create_session("Test Policy")
    db.save_message(session_id, "user", "What is the deductible?")
    db.save_message(session_id, "assistant", "It is INR 1,000.", {"citations": [{"source": "schedule.pdf", "page_number": 1}]})
    messages = db.get_messages(session_id)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["metadata"]["citations"][0]["page_number"] == 1
    assert len(db.list_sessions("Test Policy")) == 1


def test_delete_session_cascades_messages(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    session_id = db.create_session("Test Policy")
    db.save_message(session_id, "user", "hello")
    db.delete_session(session_id)
    assert db.get_messages(session_id) == []
