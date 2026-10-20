"""Connectors fetch raw records from a source system, one connector per system.

Every connector, mock or live, yields the same shape, so the rest of the pipeline never
needs to know which one it is talking to:

    (record_type, external_id, payload)

where payload is the record exactly as the source would send it.
"""


class Connector:
    """Base for all connectors. Subclasses set `source_code` and implement `fetch`."""

    source_code = ""

    def fetch(self):
        """Yield (record_type, external_id, payload) tuples."""
        raise NotImplementedError
