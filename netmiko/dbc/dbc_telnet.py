# netmiko/dbc/dbc_telnet.py
import re
import time
import logging
from netmiko.cisco_base_connection import CiscoBaseConnection

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Set up logging for debugging paging issues
log = logging.getLogger(__name__)


class DbcTelnet(CiscoBaseConnection):
    pri_prompt_terminator = r"#"
    alt_prompt_terminator = r">"
    config_mode_prompt = r"\(config[^\)]*\)#"
    ansi_escape_codes = True

    def session_preparation(self) -> None:
        # coax a real prompt first
        self.write_channel("\r\n")
        self.read_until_pattern(pattern=r"[>#]\s*$", read_timeout=60)
        self.set_base_prompt()

        # disable paging (try a few; keep whichever your box supports)
        paging_commands = ("terminal length 0", "scroll 512", "page off", "no page")
        for cmd in paging_commands:
            try:
                self.write_channel(cmd + "\r\n")
                self.read_until_pattern(pattern=r"[>#]\s*$", read_timeout=3)
                log.debug(f"Successfully disabled paging with: {cmd}")
                break
            except Exception as e:
                log.debug(f"Paging command '{cmd}' failed: {e}")
                continue
        else:
            log.warning("All paging disable commands failed - paging may still be active")

    def set_base_prompt(self, *args, **kwargs) -> str:
        try:
            prompt = self.find_prompt().strip()
        except Exception as e:
            raise ValueError(f"Could not determine device prompt: {e}")
        
        if not prompt:
            raise ValueError("Empty prompt received from device")
        
        # Clean up the prompt
        prompt = ANSI_RE.sub("", prompt)                    # strip ANSI escape codes
        prompt = re.sub(r"\x08+.", "", prompt)              # strip backspaces + following char(s)
        prompt = re.sub(r"[>#]\s*$", "", prompt)            # drop terminator
        prompt = re.sub(r"\([^)]*\)\s*$", "", prompt)       # drop (config...) suffixes
        
        self.base_prompt = prompt.strip()
        
        if not self.base_prompt:
            raise ValueError("Base prompt is empty after cleaning")
        
        log.debug(f"Set base prompt to: '{self.base_prompt}'")
        return self.base_prompt

    def check_config_mode(
        self, check_string: str = ")#", pattern: str = r"#\s*$", force_regex: bool = False
    ) -> bool:
        # drain pager if needed, then nudge a prompt
        self._drain_pager()
        self.write_channel("\r\n")
        try:
            self.read_until_pattern(pattern=pattern, read_timeout=20)
        except Exception as e:
            log.debug(f"Failed to get prompt in check_config_mode: {e}")
            return False
        return super().check_config_mode(check_string=check_string, pattern=pattern)

    def _drain_pager(self) -> None:
        """
        Drain any paging prompts (--More--) by sending spaces until we get back to a normal prompt.
        Uses timeout-based approach for robustness.
        """
        start_time = time.time()
        timeout = 30  # 30 second timeout
        
        while time.time() - start_time < timeout:
            buf = self.read_channel()
            
            # Check for various paging patterns
            if any(pattern in buf for pattern in ["--More--", "-- More --", "(more)", "Press any key"]):
                log.debug("Found paging prompt, sending space to continue")
                self.write_channel(" ")
                time.sleep(0.1)
                continue
            
            # Check if we're back to a normal prompt
            if re.search(r"[>#]\s*$", buf, re.MULTILINE):
                log.debug("Found normal prompt, pager drained successfully")
                break
                
            # If no paging and no prompt, we might be done
            if buf.strip() == "":
                break
                
            time.sleep(0.1)
        else:
            log.warning(f"Pager draining timed out after {timeout} seconds")

    def send_command(self, command_string: str, **kwargs) -> str:
        """
        Override send_command to handle paging issues more gracefully.
        """
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