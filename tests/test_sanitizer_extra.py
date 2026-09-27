from core.sanitizer import (
    SecretFilter,
    sanitize_command_for_log,
    sanitize_input_string,
    sanitize_log_line,
    sanitize_url,
)


def test_sanitize_url():
    assert sanitize_url("") == ""
    assert sanitize_url(None) == ""
    assert sanitize_url("http://user:pass@localhost") == "http://user:********@localhost"
    assert sanitize_url("http://pass@localhost") == "http://********@localhost"
    assert sanitize_url("http://localhost/?token=123") == "http://localhost/?token=********"
    assert sanitize_url("http://localhost/?password=abc&other=1") == "http://localhost/?password=********&other=1"


def test_sanitize_url_exception():
    assert sanitize_url("http://[invalid_url") == "http://[invalid_url"


def test_sanitize_log_line_empty():
    assert sanitize_log_line("") == ""
    assert sanitize_log_line(None) == ""


def test_sanitize_command_for_log_string():
    assert sanitize_command_for_log("srt://127.0.0.1?passphrase=123") == "srt://127.0.0.1?passphrase=********"


def test_sanitize_input_string():
    assert sanitize_input_string("hello\x00world") == "helloworld"
    assert sanitize_input_string("hello\x01world") == "helloworld"
    assert sanitize_input_string(None) == ""
    assert sanitize_input_string(123) == "123"


def test_secret_filter():
    f = SecretFilter()

    class DummyRecord:
        def __init__(self, msg, args):
            self.msg = msg
            self.args = args

        def getMessage(self):
            return str(self.msg) % self.args if self.args else str(self.msg)

    r = DummyRecord("token=%s", ("123",))
    assert f.filter(r) is True
    assert r.msg == "token=********"
    assert r.args == ()

    r2 = DummyRecord("token=123", ())
    assert f.filter(r2) is True
    assert r2.msg == "token=********"

    r3 = DummyRecord(123, (1,))  # Trigger args branch
    r3.getMessage = lambda: 1 / 0
    assert f.filter(r3) is True
