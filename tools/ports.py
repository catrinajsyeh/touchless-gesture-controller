"""Find a likely Freenove USB serial port without claiming it is the right one."""

from serial.tools import list_ports


def candidates():
    ranked = []
    for port in list_ports.comports():
        score = 0
        if port.vid == 0x303A:
            score += 3
        if port.vid == 0x1A86:
            score += 2
        text = f"{port.description or ''} {port.manufacturer or ''}".lower()
        if "esp" in text or "ch340" in text or "ch343" in text or "usb serial" in text or "uart" in text:
            score += 1
        ranked.append((score, port.device, port.description or ""))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked


def choose(explicit=None):
    if explicit:
        return explicit
    ranked = candidates()
    if not ranked:
        return None
    if ranked[0][0] > 0:
        return ranked[0][1]
    if len(ranked) == 1:
        return ranked[0][1]
    return None
