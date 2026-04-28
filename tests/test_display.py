"""Test the display"""

import io

from pytimer.display import Display


class _Cp1252LikeOutput(io.StringIO):
    encoding = "cp1252"

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        return super().write(text)


def test_display_falls_back_when_output_encoding_cannot_encode_text() -> None:
    output = _Cp1252LikeOutput()
    display = Display(output=output, ansi=False)

    display.render("progress █░")

    assert output.getvalue() == "progress ??\n"
