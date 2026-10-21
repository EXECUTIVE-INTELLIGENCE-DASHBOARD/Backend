from ..connectors.assets import MockAssetRegisterConnector
from ..loaders.assets import load_asset_register
from . import Source

SOURCE = Source(
    code="assets",
    name="Asset Register",
    mock_connector=MockAssetRegisterConnector,
    loader=load_asset_register,
)
