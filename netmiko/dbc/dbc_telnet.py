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

    def normalize_linefeeds(self, a_string: str) -> str:
        """Convert '\r\r\n','\r\n', '\n\r' to '\n'."""
        newline = re.sub(r"\r\r\n|\r\n|\n\r", "\n", a_string)
        return newline

    def strip_prompt(self, a_string: str) -> str:
        """Strip the trailing router prompt from the output."""
        # More flexible prompt stripping for DBC devices
        response_list = a_string.split("\n")
        if response_list:
            last_line = response_list[-1]
            # Check if last line looks like a DBC prompt
            if re.search(r".*#\s*$", last_line):
                return "\n".join(response_list[:-1])
        return a_string

    def find_prompt(self, delay_factor: float = 1.0, pattern: Optional[str] = None) -> str:
        """
        Finds the current network device prompt, last line only.
        
        For DBC devices, we need to handle both config and exec mode prompts.
        """
        if pattern is None:
            # DBC devices use # as terminator, with optional (config) part
            pattern = r"[^\r\n]*#\s*$"
        
        delay_factor = self.select_delay_factor(delay_factor)
        sleep_time = delay_factor * 0.25
        self.clear_buffer()
        self.write_channel(self.RETURN)
        
        # Give the device time to respond
        import time
        time.sleep(sleep_time)
        
        # Read the output
        output = self.read_channel()
        
        # Find the prompt in the output
        output = self.normalize_linefeeds(output)
        lines = output.split('\n')
        
        # Look for the prompt in the last few lines
        for line in reversed(lines):
            line = line.strip()
            if line and re.search(pattern, line):
                return line
        
        # If no prompt found, raise an error
        raise ValueError(f"Unable to find prompt in output: {repr(output)}")

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