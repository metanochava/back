"""Every date printed on a health PDF is written out ({{ value|long_date }})."""
import datetime

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from saude.templatetags.clinic import long_date


class LongDateFilterTests(SimpleTestCase):
    def test_a_date(self):
        self.assertEqual(long_date(datetime.date(2026, 11, 8)), "08 de Novembro de 2026")

    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Maputo")
    def test_a_datetime_in_local_time_with_the_time(self):
        value = datetime.datetime(2026, 11, 8, 22, 30, tzinfo=datetime.timezone.utc)
        self.assertEqual(long_date(value), "09 de Novembro de 2026")
        self.assertEqual(long_date(value, "time"), "09 de Novembro de 2026 às 00:30")

    def test_empty_values_print_nothing(self):
        self.assertEqual(long_date(None), "")
        self.assertEqual(long_date(""), "")

    def test_in_a_template(self):
        html = Template('{% load clinic %}{{ d|long_date|default:"-" }}|{{ n|long_date|default:"-" }}').render(
            Context({"d": datetime.date(2010, 6, 11), "n": None}))
        self.assertEqual(html, "11 de Junho de 2010|-")
