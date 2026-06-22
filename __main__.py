"""Run the KMSWC GUI:  python -m kmswc"""

from .presentation.gui import build_app


def main() -> None:
    build_app().mainloop()


if __name__ == "__main__":
    main()
