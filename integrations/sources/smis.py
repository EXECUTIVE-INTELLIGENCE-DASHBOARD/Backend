from ..connectors.smis import MockSMISConnector
from ..loaders.smis import load_smis
from . import Source

SOURCE = Source(
    code="smis",
    name="School Management Information System",
    mock_connector=MockSMISConnector,
    loader=load_smis,
)
