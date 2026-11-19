from blackbox.winio import decode_console


def test_decode_console_cp874():
    raw = "สถานะ : เชื่อมต่อแล้ว".encode("cp874")
    assert decode_console(raw) == "สถานะ : เชื่อมต่อแล้ว"


def test_decode_console_utf8():
    raw = "hello".encode("utf-8")
    assert decode_console(raw) == "hello"
