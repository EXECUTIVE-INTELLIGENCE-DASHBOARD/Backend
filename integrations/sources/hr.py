from ..connectors.hr import MockHRConnector
from ..loaders.hr import load_hr
from . import Source

SOURCE = Source(
    code="hr",
    name="HR System",
    mock_connector=MockHRConnector,
    loader=load_hr,
)
