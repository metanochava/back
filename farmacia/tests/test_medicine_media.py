"""Catalogue medicine media: a main photo (MedicineCatalogItem.image) and a
gallery of photos and videos (MedicineCatalogMedia), shown in the
marketplace search."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import serializers
from rest_framework.test import APIClient

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity_user import EntityUser
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.user import User

from farmacia.models import MedicineCatalogMedia
from farmacia.models.medicine_catalog_media import MAX_MEDIA_PER_ITEM
from farmacia.serializers.medicine_catalog_item import validate_photo_size
from farmacia.serializers.medicine_catalog_media import MedicineCatalogMediaSerializer
from farmacia.tests.test_marketplace import MarketplaceTestCase

ITEMS = "/api/farmacia/medicinecatalogitems/"
MEDIA_URL = "/api/farmacia/medicinecatalogmedia/"
MEDIA = tempfile.mkdtemp(prefix="farmacia-media-")


def png(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def mp4(name="howto.mp4", size=64):
    return SimpleUploadedFile(name, b"\x00" * size, content_type="video/mp4")


@override_settings(MEDIA_ROOT=MEDIA)
class MedicineMediaTests(MarketplaceTestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.root = self.near.client  # tests' shared "Root" group: every CRUD permission

    def add_media(self, item, client=None, file=None, **extra):
        return (client or self.root).post(MEDIA_URL, {"catalog_item": str(item.id), "file": file or png(), **extra},
                                          format="multipart")

    def test_main_photo_is_stored_under_the_catalogue_item(self):
        response = self.root.patch(f"{ITEMS}{self.paracetamol.id}/", {"image": png()}, format="multipart")

        self.assertIn(response.status_code, (200, 202), response.content)
        self.paracetamol.refresh_from_db()
        self.assertTrue(self.paracetamol.image.name.startswith(f"farmacia/catalogue/{self.paracetamol.id}/"))
        self.assertIn("token=", response.json()["image"]["url"])
        self.assertEqual(response.json()["image"]["kind"], "image")

    def test_gallery_photos_and_videos_are_listed_per_medicine_in_order(self):
        self.assertEqual(self.add_media(self.paracetamol, caption="Box", position=2).status_code, 201)
        response = self.add_media(self.paracetamol, file=mp4(), caption="How to use", position=1)
        self.assertEqual(response.status_code, 201, response.content)
        self.add_media(self.syrup, caption="Bottle")

        rows = self.root.get(MEDIA_URL, {"catalog_item": str(self.paracetamol.id)}).json()["results"]

        self.assertEqual([(row["caption"], row["file"]["kind"]) for row in rows], [("How to use", "video"), ("Box", "image")])
        media = MedicineCatalogMedia.objects.get(caption="Box")
        self.assertTrue(media.file.name.startswith(f"farmacia/catalogue/{self.paracetamol.id}/"))

    def test_a_medicine_has_at_most_ten_photos_or_videos(self):
        for _ in range(MAX_MEDIA_PER_ITEM):
            self.assertEqual(self.add_media(self.paracetamol).status_code, 201)

        response = self.add_media(self.paracetamol)

        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 10", str(response.json()["error"]))
        self.assertEqual(self.add_media(self.syrup).status_code, 201)  # per medicine

    def test_only_photos_and_videos_within_their_size_are_accepted(self):
        text = SimpleUploadedFile("leaflet.txt", b"not an image", content_type="text/plain")
        self.assertEqual(self.add_media(self.paracetamol, file=text).status_code, 400)
        fake = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        self.assertEqual(self.add_media(self.paracetamol, file=fake).status_code, 400)

        big_video = mp4()
        big_video.size = 50 * 1024 * 1024 + 1
        with self.assertRaises(serializers.ValidationError):
            MedicineCatalogMediaSerializer().validate_file(big_video)
        big_photo = png()
        big_photo.size = 5 * 1024 * 1024 + 1
        with self.assertRaises(serializers.ValidationError):
            MedicineCatalogMediaSerializer().validate_file(big_photo)
        with self.assertRaises(serializers.ValidationError):
            validate_photo_size(None, big_photo)  # the main photo too
        self.assertFalse(MedicineCatalogMedia.objects.exists())

    def test_writing_media_needs_the_permission(self):
        group = Group.objects.create(name="Media plain")
        user = User.objects.create_user(username="photos-plain", email="photos-plain@example.com",
                                        password="x-pass-123")
        EntityUser.objects.create(entity=self.near.entity, user=user)
        BranchUser.objects.create(branch=self.near.branch, user=user)
        BranchUserGroup.objects.create(branch=self.near.branch, user=user, group=group)
        token = ResaasContextService.issue(user=user, entity_id=self.near.entity.id, branch_id=self.near.branch.id,
                                           group_id=group.id)["token"]
        client = APIClient()
        client.force_authenticate(user=user)
        client.credentials(HTTP_X_RESAAS_CONTEXT=token, HTTP_L="1")

        self.assertEqual(self.add_media(self.paracetamol, client=client).status_code, 403)
        self.assertEqual(client.patch(f"{ITEMS}{self.paracetamol.id}/", {"image": png()},
                                      format="multipart").status_code, 403)
        self.assertFalse(MedicineCatalogMedia.objects.exists())

    def test_marketplace_search_shows_the_main_photo_and_the_gallery(self):
        self.root.patch(f"{ITEMS}{self.paracetamol.id}/", {"image": png()}, format="multipart")
        self.add_media(self.paracetamol, caption="Box", position=1)
        self.add_media(self.paracetamol, file=mp4(), caption="How to use", position=2)

        rows = self.search(q="paracetamol 500").json()["results"]

        medicine = rows[0]["medicine"]
        self.assertIn("token=", medicine["image"])
        self.assertEqual([(m["caption"], m["kind"]) for m in medicine["media"]], [("Box", "image"), ("How to use", "video")])
        self.assertTrue(all("token=" in m["url"] for m in medicine["media"]))
        # a medicine without media says so, never a placeholder URL
        syrup = self.search(q="paracetamol 120").json()["results"][0]["medicine"]
        self.assertIsNone(syrup["image"])
        self.assertEqual(syrup["media"], [])
