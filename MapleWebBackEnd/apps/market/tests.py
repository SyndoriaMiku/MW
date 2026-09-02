from django.test import SimpleTestCase

from .views import ListingViewSet, TradeViewSet


class MarketMutationSurfaceTests(SimpleTestCase):
    def test_listing_does_not_expose_generic_update_methods(self):
        self.assertNotIn('put', ListingViewSet.http_method_names)
        self.assertNotIn('patch', ListingViewSet.http_method_names)

    def test_trade_changes_only_through_explicit_actions(self):
        self.assertNotIn('put', TradeViewSet.http_method_names)
        self.assertNotIn('patch', TradeViewSet.http_method_names)
        self.assertNotIn('delete', TradeViewSet.http_method_names)
