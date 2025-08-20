from typing import Optional
from netmiko.cisco.cisco_ios import CiscoIosBase


class DbcTelnet(CiscoIosBase):
    """DBC Telnet driver - same as Cisco IOS but without 16-char prompt truncation."""

    def set_base_prompt(
        self,
        pri_prompt_terminator: str = "#",
        alt_prompt_terminator: str = ">",
        delay_factor: float = 1.0,
        pattern: Optional[str] = None,
    ) -> str:
        """
        Sets self.base_prompt for DBC devices.
        
        Identical to CiscoIosBase.set_base_prompt() but does NOT truncate to 16 characters.
        """
        # This is exactly the same as CiscoIosBase.set_base_prompt()
        # but without the [:16] truncation at the end
        base_prompt = super(CiscoIosBase, self).set_base_prompt(
            pri_prompt_terminator=pri_prompt_terminator,
            alt_prompt_terminator=alt_prompt_terminator,
            delay_factor=delay_factor,
            pattern=pattern,
        )
        
        # CiscoIosBase does: self.base_prompt = base_prompt[:16]  
        # DBC does: self.base_prompt = base_prompt (no truncation)
        self.base_prompt = base_prompt
        return self.base_prompt