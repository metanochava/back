from saude.views.address_throttle import _AddressThrottle


class PublicBookingReadThrottle(_AddressThrottle):
    scope = "saude_public_booking_read"
    setting = "SAUDE_PUBLIC_BOOKING_READ_THROTTLE_RATE"
    default_rate = "300/hour"
