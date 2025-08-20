import re
from typing import Optional
from netmiko.cisco_base_connection import CiscoBaseConnection


class DbcTelnet(CiscoBaseConnection):
    """DBC OLT Telnet driver."""

    def session_preparation(self) -> None:
        """Prepare session: get prompt, disable paging."""
        self._test_channel_read(pattern=r"#")
        self.set_base_prompt()
        self.disable_paging()

    def set_base_prompt(
        self,
        pri_prompt_terminator: str = "#",
        alt_prompt_terminator: str = ">",
        delay_factor: float = 1.0,
        pattern: Optional[str] = None,
    ) -> str:
        """Set base prompt without truncation and with ANSI cleaning."""
        prompt = self.find_prompt(delay_factor=delay_factor, pattern=pattern).strip()
        
        prompt = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", prompt)  # ANSI
        prompt = re.sub(r"\x08+.", "", prompt)                     # backspaces
        
        if prompt.endswith(pri_prompt_terminator):
            prompt = prompt[:-len(pri_prompt_terminator)]
        
        prompt = re.sub(r"\([^)]*\)\s*$", "", prompt)
        
        self.base_prompt = prompt.strip()
        return self.base_prompt

    def disable_paging(
        self,
        command: str = "terminal length 0",
        delay_factor: Optional[float] = None,
        cmd_verify: bool = True,
        pattern: Optional[str] = None,
    ) -> str:
        """Disable paging - matches BaseConnection signature."""
        # Use the parent's implementation to ensure correct return type
        return super().disable_paging(
            command=command,
            delay_factor=delay_factor,
            cmd_verify=cmd_verify,
            pattern=pattern,
        )

    def find_prompt(self, delay_factor: float = 1.0, pattern: Optional[str] = None) -> str:
        """Find prompt, handling --More-- if present."""
        output = self.read_channel()
        
        while "--More--" in output:
            self.write_channel(" ")
            output = self.read_channel()
        
        return super().find_prompt(delay_factor=delay_factor, pattern=pattern)