# src/sources/

This directory contains the implementations for various MTBO event data sources.

## Contents

- `base_source.py`: Defines the `BaseSource` abstract base class.
- `eventor_source.py`: Fetches event lists and details from Eventor instances.
- `eventor_parser.py`: Complex logic for parsing Eventor HTML.
- `manual_source.py`: Loads events from local JSON files (non-Eventor sources).

## Adding a New Source

1.  Inherit from `BaseSource`.
2.  Implement `fetch_events()`.
3.  Type hint all methods explicitly.
