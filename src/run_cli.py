#!/usr/bin/env python3
from interface.cli import KarbotCLI

def main():
    cli = KarbotCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()

