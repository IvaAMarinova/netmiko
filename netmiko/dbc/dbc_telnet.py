from typing import Optional
import re
from netmiko.cisco.cisco_ios import CiscoIosBase


class DbcBase(CiscoIosBase):
    """Base class for DBC devices with proper prompt handling."""

    def set_base_prompt(
        self,
        pri_prompt_terminator: str = "#",
        alt_prompt_terminator: str = "",
        delay_factor: float = 1.0,
        pattern: Optional[str] = None,
    ) -> str:
        """
        Set base prompt for DBC devices using proper pattern matching.
        
        DBC devices use format: hostname# or hostname(config)#
        The base prompt should be just the hostname part without (config).
        """
        # DBC devices primarily use # as terminator
        if pattern is None:
            pattern = r"#\s*$"
        
        # Get the current prompt
        prompt = self.find_prompt(delay_factor=delay_factor, pattern=pattern)
        
        if not prompt.endswith("#"):
            raise ValueError(f"DBC prompt not found or invalid: {repr(prompt)}")
        
        # Remove the # terminator
        base_prompt = prompt[:-1].strip()
        
        # Remove (config) or (config-*) parts if present
        # This handles: hostname(config)# -> hostname
        #              hostname(config-if)# -> hostname  
        config_pattern = r'\(config[^)]*\)$'
        base_prompt = re.sub(config_pattern, '', base_prompt).strip()
        
        # Don't truncate like Cisco IOS does - keep the full hostname
        self.base_prompt = base_prompt
        return self.base_prompt

    def check_config_mode(
        self,
        check_string: str = "(config",
        pattern: str = r"#\s*$",
        force_regex: bool = False,
    ) -> bool:
        """
        Check if device is in configuration mode.
        
        DBC devices use (config) in the prompt when in configuration mode:
        - Config mode: hostname(config)#
        - Exec mode: hostname#
        """
        # Get current prompt
        current_prompt = self.find_prompt()
        
        # Check if we're in config mode by looking for (config) pattern
        if check_string in current_prompt:
            return True
        
        # Not in config mode
        return False


class DbcTelnet(DbcBase):
    """DBC Telnet driver that properly handles prompt detection without truncation."""
    
    def session_preparation(self) -> None:
        """Prepare the session after the connection has been established."""
        # DBC devices log in directly to config mode, so we just need to set the base prompt
        self.set_base_prompt()