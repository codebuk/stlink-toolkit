"""Allow ``python3 -m stlink_toolkit`` to invoke the CLI.

This avoids the RuntimeWarning about module re-entry that occurs when the
package is imported (which imports cli.py as a submodule) and then
``python3 -m stlink_toolkit.cli`` tries to re-execute the same module as
``__main__``.
"""

from .cli import main

if __name__ == "__main__":
    main()
