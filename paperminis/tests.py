from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model, get_user
from django.contrib.auth.models import Group
from unittest.mock import patch
import json
import numpy as np
from paperminis.generate_minis import MiniBuilder, crop_whitespace
from paperminis.models import Bestiary, Creature, CreatureQuantity, PrintSettings
from paperminis.utils import handle_json
# Create your tests here.

class QuickViewTests(TestCase):
    """Testing basic view functionality"""
    def test_quickbuild(self):
        response = self.client.get('/quickbuild/')
        self.assertEqual(response.status_code, 200)

    def test_index(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_CreatureView_anon(self):
        response = self.client.get('/creatures/')
        self.assertEqual(response.status_code, 302)

    def test_BestiaryView_anon(self):
        response = self.client.get('/bestiaries/')
        self.assertEqual(response.status_code, 302)

    def test_login_view(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)

    def test_signup_view(self):
        response = self.client.get('/signup/')
        self.assertEqual(response.status_code, 200)


class AccountTests(TestCase):

    def setUp(self):
        self.email = 'testuser@email.com'
        self.password = 'MyPassword1234$'
        self.group = Group(name='temp')
        self.group.save()

    def test_signup_page_url(self):
        response = self.client.get("/signup/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name='signup.html')

    def test_signup_page_view_name(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name='signup.html')

    def test_signup_form(self):
        response = self.client.post(reverse('signup'), data={
            'email': self.email,
            'password1': self.password,
            'password2': self.password
        })
        self.assertEqual(response.status_code, 302)
        users = get_user_model().objects.all()
        self.assertEqual(users.count(), 1)


class AuthenticatedViewsTests(TestCase):

    def setUp(self):
        self.email = 'testuser@email.com'
        self.password = 'MyPassword1234$'
        self.group = Group(name='temp')
        self.group.save()
        self.user = get_user_model().objects.create_user(email=self.email, password=self.password)
        self.client.login(email=self.email, password=self.password)

    def test_BestiaryView_auth(self):
        response = self.client.get('/bestiaries/')
        self.assertEqual(response.status_code, 200)

    def test_CreatureView_auth(self):
        response = self.client.get('/creatures/')
        self.assertEqual(response.status_code, 200)


class BestiaryCreaturesTests(TestCase):

    def setUp(self):
        self.email = 'testuser@email.com'
        self.password = 'MyPassword1234$'
        self.group = Group(name='temp')
        self.group.save()
        self.user = get_user_model().objects.create_user(email=self.email, password=self.password)
        self.client.login(email=self.email, password=self.password)

    def test_create_bestiary(self):
        response = self.client.post(reverse('bestiary-create'), data={
            'name': "test bestiary",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Bestiary.objects.first().name, "test bestiary")
        self.assertEqual(Bestiary.objects.all().count(), 1)
        self.assertEqual(Bestiary.objects.first().owner, self.user)

    def test_create_creatures(self):
        response = self.client.post(reverse('creature-create'), data={
            'name': "test creature",
            'img_url': "https://i.imgur.com/lVe3YlI.jpg",
            'show_name': "true",
            'size': 'M',
            'position': 'bottom',
            'color': 'a9a9a9'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Creature.objects.first().name, "test creature")
        self.assertEqual(Creature.objects.all().count(), 1)
        self.assertEqual(Creature.objects.first().owner, self.user)

    def test_create_ddb_enc(self):
        response = self.client.post(reverse('ddb-enc-bestiary-create'), data={
            'ddb_enc_url': "https://www.dndbeyond.com/encounters/905d737c-b647-4885-b8bf-51c73ecd1231"
        })
        self.assertEqual(Creature.objects.all().count(), 10)
        self.assertEqual(Bestiary.objects.all().count(), 1)
        self.assertEqual(Bestiary.objects.first().name, "TEST-Forge ALL + Many")


class CropWhitespaceTests(TestCase):
    """Testing the whitespace cropping helper."""

    def _bordered(self, size=400, content=100):
        img = np.full((size, size, 3), 255, np.uint8)
        start = (size - content) // 2
        img[start:start + content, start:start + content] = (0, 0, 255)
        return img

    def test_crops_uniform_border(self):
        img = self._bordered()
        out = crop_whitespace(img)
        self.assertLess(out.shape[0], img.shape[0])
        self.assertLess(out.shape[1], img.shape[1])

    def test_solid_image_unchanged(self):
        img = np.zeros((200, 200, 3), np.uint8)
        out = crop_whitespace(img)
        self.assertEqual(out.shape, img.shape)

    def test_tiny_content_unchanged(self):
        img = np.full((400, 400, 3), 255, np.uint8)
        img[200, 200] = (0, 0, 0)
        out = crop_whitespace(img)
        self.assertEqual(out.shape, img.shape)


class MiniBuilderCropTests(TestCase):
    """Testing that enabling whitespace cropping increases mini real estate."""

    def setUp(self):
        self.group = Group(name='temp')
        self.group.save()
        self.user = get_user_model().objects.create_user(email='test@email.com', password='MyPassword1234$')

    def _bordered_img(self, size=400, content=100):
        img = np.full((size, size, 3), 255, np.uint8)
        start = (size - content) // 2
        img[start:start + content, start:start + content] = (0, 0, 255)
        return img

    @patch('paperminis.generate_minis.download_image')
    def test_crop_flag_increases_content(self, mock_download):
        mock_download.return_value = self._bordered_img()
        creature = Creature.objects.create(
            name="Test", owner=self.user,
            img_url="https://example.com/img.jpg",
            size="M", position="bottom", show_name=False,
        )

        builder = MiniBuilder()
        builder.load_settings(crop_whitespace=False)
        mini_no_crop = builder.build_mini(creature)
        self.assertIsNot(mini_no_crop, 'Object is not a Creature.')

        builder = MiniBuilder()
        builder.load_settings(crop_whitespace=True)
        mini_crop = builder.build_mini(creature)

        red_no_crop = int(np.sum(np.all(mini_no_crop == (0, 0, 255), axis=2)))
        red_crop = int(np.sum(np.all(mini_crop == (0, 0, 255), axis=2)))
        self.assertGreater(red_crop, red_no_crop)

    def test_printsettings_crop_whitespace_default(self):
        ps = PrintSettings.objects.create(user=self.user)
        self.assertFalse(ps.crop_whitespace)
        ps.crop_whitespace = True
        ps.save()
        ps.refresh_from_db()
        self.assertTrue(ps.crop_whitespace)


class HandleJsonTests(TestCase):
    """Testing the JSON import helper."""

    def setUp(self):
        self.group = Group(name='temp')
        self.group.save()
        self.user = get_user_model().objects.create_user(email='test@email.com', password='MyPassword1234$')

    def _upload(self, data):
        from django.core.files.uploadedfile import SimpleUploadedFile
        payload = json.dumps(data).encode('utf-8')
        f = {'file': SimpleUploadedFile('creatures.json', payload)}
        return handle_json(f, self.user)

    def test_fresh_import_creates_creatures(self):
        data = {
            "orc": {"img_url": "https://example.com/orc.jpg", "name": "orc", "creature_size": "Medium"},
            "dragon": {"img_url": "https://example.com/dragon.jpg", "name": "dragon", "creature_size": "Gargantuan"},
        }
        skipped = self._upload(data)
        self.assertEqual(skipped, 0)
        self.assertEqual(Creature.objects.filter(owner=self.user).count(), 2)

    def test_import_with_existing_creature_does_not_crash(self):
        Creature.objects.create(owner=self.user, name="orc", img_url="https://example.com/orc.jpg", size="M")
        data = {
            "orc": {"img_url": "https://example.com/orc.jpg", "name": "orc", "creature_size": "Medium"},
            "goblin": {"img_url": "https://example.com/goblin.jpg", "name": "goblin", "creature_size": "Small"},
        }
        skipped = self._upload(data)
        # existing creature is skipped, new one is created
        self.assertEqual(skipped, 1)
        self.assertEqual(Creature.objects.filter(owner=self.user).count(), 2)

    def test_import_updates_size_of_existing_creature(self):
        Creature.objects.create(owner=self.user, name="orc", img_url="https://example.com/orc.jpg", size="L")
        data = {
            "orc": {"img_url": "https://example.com/orc.jpg", "name": "orc", "creature_size": "Medium"},
        }
        skipped = self._upload(data)
        self.assertEqual(skipped, 0)
        creature = Creature.objects.get(owner=self.user, name="orc")
        self.assertEqual(creature.size, "M")
