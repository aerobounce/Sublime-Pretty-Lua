#!/usr/bin/env python
# coding: utf-8
#
# Pretty Lua.py
#
# AGPLv3 License
# Created by github.com/aerobounce on 2020/07/19.
# Copyright © 2020-2022, aerobounce. All rights reserved.
#

from html import escape
from os import R_OK
from os import path, access
from re import compile
from subprocess import PIPE
from subprocess import Popen

from sublime import LAYOUT_BELOW
from sublime import Edit, Phantom, PhantomSet, Region, View
from sublime import error_message as alert, expand_variables, load_settings, packages_path
from sublime_plugin import TextCommand, ViewEventListener

SETTINGS_FILENAME = "Pretty Lua.sublime-settings"
ON_CHANGE_TAG = "reload_settings"
UTF_8 = "utf-8"
PHANTOM_STYLE = """
<style>
    div.error-arrow {
        border-top: 0.4rem solid transparent;
        border-left: 0.5rem solid color(var(--redish) blend(var(--background) 30%));
        width: 0;
        height: 0;
    }
    div.error {
        padding: 0.4rem 0 0.4rem 0.7rem;
        margin: 0 0 0.2rem;
        border-radius: 0 0.2rem 0.2rem 0.2rem;
    }
    div.error span.message {
        padding-right: 0.7rem;
    }
    div.error a {
        text-decoration: inherit;
        padding: 0.35rem 0.7rem 0.45rem 0.8rem;
        position: relative;
        bottom: 0.05rem;
        border-radius: 0 0.2rem 0.2rem 0;
        font-weight: bold;
    }
    html.dark div.error a {
        background-color: #00000018;
    }
    html.light div.error a {
        background-color: #ffffff18;
    }
</style>
"""


def plugin_loaded():
    PrettyLua.settings = load_settings(SETTINGS_FILENAME)
    PrettyLua.reload_settings()
    PrettyLua.settings.add_on_change(ON_CHANGE_TAG, PrettyLua.reload_settings)


def plugin_unloaded():
    PrettyLua.settings.clear_on_change(ON_CHANGE_TAG)


class PrettyLua:
    settings = load_settings(SETTINGS_FILENAME)
    phantom_sets = {}
    shell_command = ""
    shell_cwd = ""
    last_valid_config_path = ""
    format_on_save = True
    show_error_inline = True
    scroll_to_error_point = True
    config_paths = []

    @classmethod
    def reload_settings(cls):
        cls.shell_command = cls.settings.get("binary")
        cls.last_valid_config_path = ""
        cls.format_on_save = cls.settings.get("format_on_save")
        cls.show_error_inline = cls.settings.get("show_error_inline")
        cls.scroll_to_error_point = cls.settings.get("scroll_to_error_point")
        cls.config_paths = cls.settings.get("config_paths")

        # Note: For Windows only, UNC path error workaround.
        # ("CMD does not support UNC paths as current directories.")
        # This may not be needed in Sublime Text 4.
        #
        # Popen needs non UNC `cwd` to be specified.
        # It seems `cwd` can be any path as long as it's a non UNC path
        cls.shell_cwd = packages_path()

    @classmethod
    def update_phantoms(cls, view: View, stderr: str, error_point: int):
        view_id = view.id()

        if not view_id in cls.phantom_sets:
            cls.phantom_sets[view_id] = PhantomSet(view, str(view_id))

        # Create Phantom
        def phantom_content():
            # Remove unneeded text from stderr
            error_message = stderr.replace("error: error parsing: ", "")
            error_message = compile(
                r"\ \(starting from line \d+, character \d+ and ending on line \d+, character \d+\)"
            ).sub("", error_message)
            error_message = error_message.replace("additional information: ", " (")
            error_message += ")"
            error_message = error_message.capitalize()
            return (
                "<body id=inline-error>"
                + PHANTOM_STYLE
                + '<div class="error-arrow"></div><div class="error">'
                + '<span class="message">'
                + escape(error_message, quote=False)
                + "</span>"
                + "<a href=hide>"
                + chr(0x00D7)
                + "</a></div>"
                + "</body>"
            )

        new_phantom = Phantom(
            Region(error_point, view.line(error_point).b),
            phantom_content(),
            LAYOUT_BELOW,
            lambda _: view.erase_phantoms(str(view_id)),
        )
        # Store Phantom
        cls.phantom_sets[view_id].update([new_phantom])

    @staticmethod
    def parse_error_point(view: View, stderr: str):
        digits = compile(r"\d+").findall(stderr)
        if not stderr or len(digits) != 4:
            return
        line = int(digits[2]) - 1
        column = int(digits[3]) - 1
        return view.text_point(line, column)

    @staticmethod
    def is_readable_file(filepath: str):
        if path.isfile(filepath):
            return access(filepath, R_OK)
        return False

    @staticmethod
    def shell(command: str, stdin: str):
        with Popen(command, shell=True, cwd=PrettyLua.shell_cwd, stdin=PIPE, stdout=PIPE, stderr=PIPE) as shell:
            # Print command executed to the console of ST
            print("[Pretty Lua] Popen:", command)
            # Nil check to suppress linter
            if not shell.stdin or not shell.stdout or not shell.stderr:
                return ("", "")
            # Write target_text into stdin and ensure the descriptor is closed
            shell.stdin.write(stdin.encode(UTF_8))
            shell.stdin.close()
            # Read stdout and stderr
            return (shell.stdout.read().decode(UTF_8), shell.stderr.read().decode(UTF_8))

    @classmethod
    def execute_format(cls, view: View, edit: Edit):
        # Get entire string
        entire_region = Region(0, view.size())
        entire_text = view.substr(entire_region)

        # Early return
        if not entire_text:
            return

        # Base command
        shell_command = cls.shell_command

        # Use cached path
        if cls.config_paths and cls.is_readable_file(cls.last_valid_config_path):
            shell_command += ' --config-path "{}"'.format(cls.last_valid_config_path)

        # Find and use config file
        elif cls.config_paths:
            cls.last_valid_config_path = ""
            active_window = view.window()

            if active_window:
                variables = active_window.extract_variables()

                # Iterate directories to find config file
                for path_candidate in cls.config_paths:
                    config_file = expand_variables(path_candidate, variables)

                    if cls.is_readable_file(config_file):
                        shell_command += ' --config-path "{}"'.format(config_file)
                        cls.last_valid_config_path = config_file
                        break

        # Config file is not in use anymore
        else:
            cls.last_valid_config_path = ""

        # Read from STDIN
        shell_command += " -"

        # Execute shell and get output
        output = cls.shell(shell_command, entire_text)
        stdout = output[0]
        stderr = output[1]
        stderr = stderr.replace("failed to format from stdin: ", "")
        stderr = stderr.replace(")\nadditional", ") additional")
        stderr = stderr.replace("\n", "")

        # Present alert for 'command not found'
        if "command not found" in stderr:
            alert("Pretty Lua\n" + stderr)
            return

        # Parse possible error point
        error_point = cls.parse_error_point(view, stderr)

        # Present alert for other errors
        if stderr and not error_point:
            alert("Pretty Lua\n" + stderr)
            return

        # Print parsing error
        if error_point:
            print("[Pretty Lua]", stderr)

        # Store original viewport position
        original_viewport_position = view.viewport_position()

        # Replace with the result only if no error has been caught
        if stdout and not stderr:
            view.replace(edit, entire_region, stdout)

        # Update Phantoms
        view.erase_phantoms(str(view.id()))
        if cls.show_error_inline and error_point:
            cls.update_phantoms(view, stderr, error_point)

        # Scroll to the syntax error point
        if cls.scroll_to_error_point and error_point:
            view.sel().clear()
            view.sel().add(Region(error_point))
            view.show_at_center(error_point)
        else:
            # Restore viewport position
            view.set_viewport_position((0, 0), False)
            view.set_viewport_position(original_viewport_position, False)


class PrettyLuaCommand(TextCommand):
    def run(self, edit):
        PrettyLua.execute_format(self.view, edit)


class PrettyLuaListener(ViewEventListener):
    def on_pre_save(self):
        active_window = self.view.window()

        if not active_window:
            return

        is_syntax_lua = "Lua" in self.view.settings().get("syntax")
        is_extension_lua = active_window.extract_variables()["file_extension"] == "lua"

        if PrettyLua.format_on_save and (is_syntax_lua or is_extension_lua):
            self.view.run_command("pretty_lua")

    def on_close(self):
        view_id = self.view.id()

        if view_id in PrettyLua.phantom_sets:
            PrettyLua.phantom_sets.pop(view_id)
