# netmiko/dbc/dbc_telnet.py
import re
import time
import logging
from netmiko.cisco_base_connection import CiscoBaseConnection

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

log = logging.getLogger(__name__)


class DbcTelnet(CiscoBaseConnection):
    """DBC OLT Telnet driver - avoids Cisco IOS-specific behaviors."""
    
    def session_preparation(self) -> None:
        """
        Prepare session: coax prompt and disable paging.
        Avoids Cisco IOS-specific commands like 'terminal width 511'.
        """
        # Coax a real prompt first
        self.write_channel("\r\n")
        self.read_until_pattern(pattern=r"[>#]\s*$", read_timeout=60)
        
        # Set base prompt (with ANSI/backspace stripping)
        self.set_base_prompt()
        
        # Disable paging with DBC-appropriate commands (not Cisco-specific)
        self.disable_paging()

    def set_base_prompt(self, *args, **kwargs) -> str:
        """
        Set base prompt with ANSI escape and backspace stripping.
        Does not truncate like Cisco IOS (no 16-char limit).
        """
        try:
            prompt = self.find_prompt().strip()
        except Exception as e:
            raise ValueError(f"Could not determine device prompt: {e}")
        
        if not prompt:
            raise ValueError("Empty prompt received from device")
        
        # Strip ANSI escape codes and backspaces when computing base_prompt
        prompt = ANSI_RE.sub("", prompt)                    # strip ANSI escape codes
        prompt = re.sub(r"\x08+.", "", prompt)              # strip backspaces + following char(s)
        prompt = re.sub(r"[>#]\s*$", "", prompt)            # drop terminator
        prompt = re.sub(r"\([^)]*\)\s*$", "", prompt)       # drop (config...) suffixes
        
        self.base_prompt = prompt.strip()
        
        if not self.base_prompt:
            raise ValueError("Base prompt is empty after cleaning")
        
        return self.base_prompt

    def disable_paging(self, command: str = "terminal length 0", delay_factor: float = 1.0) -> str:
        """
        Disable paging with DBC-appropriate commands.
        Avoids Cisco IOS-specific paging commands.
        """
        # Try DBC/generic paging disable commands (not Cisco-specific)
        paging_commands = [
            "terminal length 0",    # Standard command
            "scroll 512",          # Some devices use this
            "page off",            # Alternative
            "no page",             # Another alternative
        ]
        
        for cmd in paging_commands:
            try:
                output = self.send_command_timing(cmd, delay_factor=delay_factor)
                log.debug(f"Successfully disabled paging with: {cmd}")
                return output
            except Exception as e:
                log.debug(f"Paging command '{cmd}' failed: {e}")
                continue
        
        log.warning("All paging disable commands failed - paging may still be active")
        return ""

    def find_prompt(self, delay_factor: float = 1.0, pattern: str = None) -> str:
        """
        Override find_prompt to handle paging situations.
        If we encounter --More--, drain it first.
        """
        # First, drain any existing pager
        self._drain_pager()
        
        # Then use the parent method
        return super().find_prompt(delay_factor=delay_factor, pattern=pattern)

    def check_config_mode(
        self, check_string: str = ")#", pattern: str = r"#\s*$", force_regex: bool = False
    ) -> bool:
        """
        Check config mode - drains pager before mode checks.
        """
        # Drain pager before mode checks - this is critical!
        self._drain_pager()
        
        # Get fresh prompt
        self.write_channel("\r\n")
        try:
            self.read_until_pattern(pattern=pattern, read_timeout=20)
        except Exception as e:
            log.debug(f"Failed to get prompt in check_config_mode: {e}")
            return False
            
        return super().check_config_mode(check_string=check_string, pattern=pattern)

    def check_enable_mode(self, check_string: str = "#") -> bool:
        """
        Override check_enable_mode to handle paging.
        """
        # Drain pager before enable mode checks too
        self._drain_pager()
        
        return super().check_enable_mode(check_string=check_string)

    def _drain_pager(self) -> None:
        """
        Aggressively drain any paging prompts.
        This is called before any prompt detection to ensure clean state.
        """
        max_attempts = 50  # Increased from previous version
        attempt = 0
        
        while attempt < max_attempts:
            buf = self.read_channel()
            
            # Check for various paging patterns
            if any(pattern in buf for pattern in ["--More--", "-- More --", "(more)", "Press any key", "Press SPACE"]):
                log.debug(f"Found paging prompt (attempt {attempt + 1}), sending space")
                self.write_channel(" ")
                time.sleep(0.2)  # Slightly longer delay
                attempt += 1
                continue
            
            # Check if we're back to a normal prompt
            if re.search(r"[>#]\s*$", buf, re.MULTILINE):
                log.debug("Found normal prompt, pager drained successfully")
                break
                
            # If buffer is empty, send a newline to coax a prompt
            if buf.strip() == "":
                self.write_channel("\r\n")
                time.sleep(0.2)
                attempt += 1
                continue
                
            # If we have content but no paging and no prompt, we might be done
            break
        
        if attempt >= max_attempts:
            log.warning(f"Pager draining reached max attempts ({max_attempts})")

    def send_command(self, command_string: str, **kwargs) -> str:
        """
        Override send_command to handle paging issues more gracefully.
        """
        # Drain pager before sending command
        self._drain_pager()
        
        try:
            return super().send_command(command_string, **kwargs)
        except Exception as e:
            # If we get a timeout or pattern error, it might be due to paging
            if any(error_type in str(e) for error_type in ["Pattern not detected", "ReadTimeout", "TimeoutError"]):
                log.warning(f"Command '{command_string}' failed, attempting to drain pager and retry: {e}")
                self._drain_pager()
                # Retry once
                return super().send_command(command_string, **kwargs)
            else:
                raise