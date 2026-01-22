import unittest

from command_protocol import render_command


class TestCommandProtocol(unittest.TestCase):
    def test_render_command_deterministic(self):
        a = render_command(
            command="X",
            input={"b": 2, "a": 1},
            constraints={"z": 9, "y": 8},
        )
        b = render_command(
            command="X",
            input={"a": 1, "b": 2},
            constraints={"y": 8, "z": 9},
        )
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("COMMAND\n"))


if __name__ == "__main__":
    unittest.main()


