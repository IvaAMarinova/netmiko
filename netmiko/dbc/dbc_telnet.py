import re
import time
import logging
from typing import Optional
from netmiko.cisco_base_connection import CiscoBaseConnection

log = logging.getLogger(__name__)


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
        try:
            prompt = self.find_prompt(delay_factor=delay_factor, pattern=pattern).strip()
        except Exception as e:
            raise ValueError(f"Could not determine device prompt: {e}")

        if not prompt:
            raise ValueError("Empty prompt received from device")

        # Clean ANSI codes and backspaces
        prompt = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", prompt)
        prompt = re.sub(r"\x08+.", "", prompt)
        prompt = re.sub(r"[>#]\s*$", "", prompt)
        prompt = re.sub(r"\([^)]*\)\s*$", "", prompt)

        self.base_prompt = prompt.strip()
        if not self.base_prompt:
            raise ValueError("Base prompt is empty after cleaning")

        return self.base_prompt

    def disable_paging(
        self,
        command: str = "terminal length 0",
        delay_factor: Optional[float] = None,
        cmd_verify: bool = True,
        pattern: Optional[str] = None,
    ) -> str:
        """Disable paging with DBC-appropriate commands."""
        paging_commands = [
            "terminal length 0",
            "scroll 512",
            "page off",
            "no page",
        ]

        for cmd in paging_commands:
            try:
                output = self.send_command_timing(cmd, delay_factor=delay_factor or 1.0)
                log.debug(f"Successfully disabled paging with: {cmd}")
                return output
            except Exception as e:
                log.debug(f"Paging command '{cmd}' failed: {e}")
                continue

        log.warning("All paging disable commands failed - paging may still be active")
        return ""

    def find_prompt(self, delay_factor: float = 1.0, pattern: Optional[str] = None) -> str:
        """Find prompt after draining any paging."""
        self._drain_pager()
        return super().find_prompt(delay_factor=delay_factor, pattern=pattern)

    def check_config_mode(
        self, check_string: str = ")#", pattern: str = r"#\s*$", force_regex: bool = False
    ) -> bool:
        """Check config mode after draining pager."""
        self._drain_pager()
        self.write_channel("\r\n")
        try:
            self.read_until_pattern(pattern=pattern, read_timeout=20)
        except Exception as e:
            log.debug(f"Failed to get prompt in check_config_mode: {e}")
            return False

        return super().check_config_mode(check_string=check_string, pattern=pattern)

    def check_enable_mode(self, check_string: str = "#") -> bool:
        """Check enable mode after draining pager."""
        self._drain_pager()
        return super().check_enable_mode(check_string=check_string)

    def send_command(self, command_string: str, **kwargs) -> str:
        """Send command with paging handling and retry logic."""
        self._drain_pager()
        
        try:
            return super().send_command(command_string, **kwargs)
        except Exception as e:
            if any(error_type in str(e) for error_type in ["Pattern not detected", "ReadTimeout", "TimeoutError"]):
                log.warning(f"Command '{command_string}' failed, attempting to drain pager and retry: {e}")
                self._drain_pager()
                return super().send_command(command_string, **kwargs)
            else:
                raise

    def _drain_pager(self) -> None:
        """Drain any paging prompts before operations."""
        max_attempts = 50
        attempt = 0

        while attempt < max_attempts:
            buf = self.read_channel()

            if any(pattern in buf for pattern in ["--More--", "-- More --", "(more)", "Press any key", "Press SPACE"]):
                log.debug(f"Found paging prompt (attempt {attempt + 1}), sending space")
                self.write_channel(" ")
                time.sleep(0.2)
                attempt += 1
                continue

            if re.search(r"[>#]\s*$", buf, re.MULTILINE):
                log.debug("Found normal prompt, pager drained successfully")
                break

            if buf.strip() == "":
                self.write_channel("\r\n")
                time.sleep(0.2)
                attempt += 1
                continue

            break
        
        if attempt >= max_attempts:
            log.warning(f"Pager draining reached max attempts ({max_attempts})")