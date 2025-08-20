from typing import Optional
from netmiko.cisco_base_connection import CiscoBaseConnection
import re
import time


class DbcTelnet(CiscoBaseConnection):
    """DBC OLT Telnet driver."""

    def session_preparation(self) -> None:
        """Prepare session: get prompt and disable paging."""
        self._test_channel_read(pattern=r"[>#]")
        self.set_base_prompt()
        self.disable_paging()

    def set_base_prompt(
        self,
        pri_prompt_terminator: str = "#",
        alt_prompt_terminator: str = ">",
        delay_factor: float = 1.0,
        pattern: Optional[str] = None,
    ) -> str:
        """Set base prompt with ANSI cleaning, no truncation."""
        prompt = self.find_prompt(delay_factor=delay_factor, pattern=pattern).strip()

        # Clean ANSI codes and backspaces
        prompt = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", prompt)
        prompt = re.sub(r"\x08+.", "", prompt)
        prompt = re.sub(r"[>#]\s*$", "", prompt)
        prompt = re.sub(r"\([^)]*\)\s*$", "", prompt)

        self.base_prompt = prompt.strip()
        return self.base_prompt

    def read_channel(self) -> str:
        """Override read_channel to handle --More-- paging."""
        output = super().read_channel()
        
        while "--More--" in output:
            self.write_channel(" ")
            time.sleep(0.1)
            new_output = super().read_channel()
            output = output.replace("--More--", "") + new_output
            
        return output