import pytest

from hw.serial_bridge import parse_sensor_line


def test_parse_text_lines():
    assert parse_sensor_line("D1:OPEN") == (1, False)
    assert parse_sensor_line("D2:CLOSED") == (2, True)
    assert parse_sensor_line("D1:closed") == (1, True)


@pytest.mark.parametrize(
    "line", ["", "foo", "D3:OPEN", "D1:unknown", "{}", '{"door":2,"closed":true}']
)
def test_parse_invalid(line):
    with pytest.raises(ValueError):
        parse_sensor_line(line)


def test_serial_bridge_simulation():
    events = []
    from hw.serial_bridge import SerialBridge

    bridge = SerialBridge(
        port="loop://",
        baudrate=9600,
        on_sensor=lambda d, c: events.append((d, c)),
        simulate_lines=["D1:OPEN", "D2:OPEN", "D2:CLOSED"],
    )
    bridge.start()
    bridge.join(timeout=1.0)
    assert events == [(1, False), (2, False), (2, True)]
