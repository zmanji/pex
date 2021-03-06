# Copyright 2020 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import

import logging
from argparse import ArgumentParser, Namespace

from pex import pex_bootstrapper
from pex.interpreter import PythonInterpreter
from pex.interpreter_constraints import UnsatisfiableInterpreterConstraintsError
from pex.pex import PEX
from pex.tools.command import Command, Error, JsonMixin, Ok, OutputMixin, Result
from pex.typing import TYPE_CHECKING
from pex.variables import ENV

if TYPE_CHECKING:
    from typing import Any, Dict, Iterator

logger = logging.getLogger(__name__)


class Interpreter(JsonMixin, OutputMixin, Command):
    """Prints the path of the preferred interpreter to run the given PEX file with, if any."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_output_option(parser, entity="Python interpreter path"),
        parser.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Print all compatible interpreters, preferred first.",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help=(
                "Provide more information about the interpreter in json format. "
                "Once: include the interpreter requirement and platform in addition to its path. "
                "Twice: include the interpreter's supported tags. "
                "Thrice: include the interpreter's environment markers and its venv affiliation, "
                "if any."
            ),
        )
        self.add_json_options(parser, entity="verbose output")

    @staticmethod
    def _find_interpreters(
        pex,  # type: PEX
        all=False,  # type: bool
    ):
        # type: (...) -> Iterator[PythonInterpreter]
        if not all:
            yield pex.interpreter
            return

        if ENV.PEX_PYTHON:
            logger.warning(
                "Ignoring PEX_PYTHON={} in order to scan for all compatible "
                "interpreters.".format(ENV.PEX_PYTHON)
            )
        for interpreter in pex_bootstrapper.iter_compatible_interpreters(
            path=ENV.PEX_PYTHON_PATH,
            interpreter_constraints=pex.pex_info().interpreter_constraints,
        ):
            yield interpreter

    def run(
        self,
        pex,  # type: PEX
        options,  # type: Namespace
    ):
        # type: (...) -> Result
        if options.indent and not options.verbose:
            logger.warning(
                "Ignoring --indent={} since --verbose mode is not enabled.".format(options.indent)
            )
        with self.output(options) as out:
            try:
                for interpreter in self._find_interpreters(pex, all=options.all):
                    if options.verbose:
                        interpreter_info = {
                            "path": interpreter.binary,
                            "requirement": str(interpreter.identity.requirement),
                            "platform": str(interpreter.platform),
                        }  # type: Dict[str, Any]
                        if options.verbose >= 2:
                            interpreter_info["supported_tags"] = [
                                str(tag) for tag in interpreter.identity.supported_tags
                            ]
                        if options.verbose >= 3:
                            interpreter_info["env_markers"] = interpreter.identity.env_markers
                            interpreter_info["venv"] = interpreter.is_venv
                            if interpreter.is_venv:
                                interpreter_info[
                                    "base_interpreter"
                                ] = interpreter.resolve_base_interpreter().binary
                        self.dump_json(options, interpreter_info, out)
                    else:
                        out.write(interpreter.binary)
                    out.write("\n")
            except UnsatisfiableInterpreterConstraintsError as e:
                return Error(str(e))

        return Ok()
