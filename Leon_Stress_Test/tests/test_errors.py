import pytest

from quantlab.errors import DataQualityError, QuantLabError
from quantlab.market.data import MarketData
from quantlab.pricing.implied import ImpliedVolError, implied_vol


def test_vol_in_percent_is_a_data_quality_error(md):
    with pytest.raises(DataQualityError, match="décimal"):
        MarketData(md.as_of, md.spots, {"SX5E": 18.0}, md.curves)


def test_old_except_valueerror_still_works(md):
    with pytest.raises(ValueError):  # attrapable aussi comme une erreur Python standard
        MarketData(md.as_of, {"SX5E": -1.0}, md.vols, md.curves)


def test_implied_vol_error_is_a_quantlab_error():
    with pytest.raises(QuantLabError):
        implied_vol(0.5, 100, 90, 0.5, 0.03)
    assert issubclass(ImpliedVolError, ValueError)
