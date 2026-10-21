from ..connectors.tills import MockTillConnector
from ..loaders.tills import load_tills
from . import Source

SOURCE = Source(
    code="tills",
    name="Outlet Tills & Stock",
    mock_connector=MockTillConnector,
    loader=load_tills,
)
