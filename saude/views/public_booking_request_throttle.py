from saude.views.address_throttle import _AddressThrottle


class PublicBookingRequestThrottle(_AddressThrottle):
    scope = "saude_public_booking_request"
    setting = "SAUDE_PUBLIC_BOOKING_THROTTLE_RATE"
    default_rate = "10/hour"
