from netmiko.cisco_base_connection import CiscoBaseConnection


class GenexisSOLT33Base(CiscoBaseConnection):
    def session_preparation(self) -> None:
        self._test_channel_read(pattern=r"[>#]")
        self.set_base_prompt()
        self.enable()
        self.config_mode()
        # The Saturn streams asynchronous alarm/log messages to the terminal
        # (monitor / vty) line. That continuous output has no quiet gap, so it
        # breaks netmiko's gap-based reads (check_config_mode inside
        # determine_current_mode, and every send_command_timing call) with
        # "continually outputting data", and intermittently fails ONU
        # operations depending on whether an alarm happens to be streaming.
        # Silence the session as early as possible. Use a prompt-anchored read
        # (expect_string) so this command survives any spew already in flight.
        self.send_command(
            "no logging monitor", expect_string=r"#", read_timeout=30
        )
        cmd = "line width 256"
        self.set_terminal_width(command=cmd, pattern=cmd)
        self.disable_paging(command="screen-rows per-page 0")
        self.clear_buffer()
        self.exit_config_mode()
        self.exit_enable_mode()

    def exit_enable_mode(self, exit_command: str = "exit") -> str:
        output = ""
        if self.check_enable_mode():
            self.write_channel(self.normalize_cmd(exit_command))
            self.read_until_pattern(pattern=exit_command)
            output += self.read_until_pattern(pattern=r">")
            if self.check_enable_mode():
                raise ValueError("Failed to exit enable mode.")
        return output


class GenexisSOLT33Telnet(GenexisSOLT33Base):
    """Genexis SOLT33 telnet driver"""

    pass
