from typing import Optional
import re
from netmiko.cisco.cisco_ios import CiscoIosBase


class DbcBase(CiscoIosBase):
    """Base class for DBC devices with proper prompt handling."""

    def set_base_prompt(
        self,
        pri_prompt_terminator: str = "#",
        alt_prompt_terminator: str = ">",
        delay_factor: float = 1.0,
        pattern: Optional[str] = None,
    ) -> str:
        """
        Set base prompt for DBC devices using proper pattern matching.
        
        Unlike Cisco IOS, this doesn't truncate the prompt to 16 characters.
        Instead, it uses pattern matching to properly detect prompts containing
        (config), #, or > terminators.
        """
        # Use the parent's parent method (BaseConnection.set_base_prompt)
        # to avoid the truncation in CiscoIosBase
        base_prompt = super(CiscoIosBase, self).set_base_prompt(
            pri_prompt_terminator=pri_prompt_terminator,
            alt_prompt_terminator=alt_prompt_terminator,
            delay_factor=delay_factor,
            pattern=pattern,
        )
        
        # Don't truncate the base_prompt like CiscoIosBase does
        # Keep the full prompt for proper pattern matching
        self.base_prompt = base_prompt
        return self.base_prompt

    def check_config_mode(
        self,
        check_string: str = "(config",
        pattern: str = r"[>#]",
        force_regex: bool = False,
    ) -> bool:
        """
        Check if device is in configuration mode.
        
        DBC devices use (config) in the prompt when in configuration mode.
        This method looks for the (config) string in the current prompt.
        """
        # Get current prompt
        current_prompt = self.find_prompt()
        
        # Check if we're in config mode by looking for (config) pattern
        if check_string in current_prompt:
            return True
        
        # Fallback to parent method for additional checks
        return super().check_config_mode(
            check_string=check_string, pattern=pattern, force_regex=force_regex
        )


class DbcTelnet(DbcBase):
    """DBC Telnet driver that properly handles prompt detection without truncation."""
    pass