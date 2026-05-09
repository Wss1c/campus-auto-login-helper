import unittest
from unittest.mock import patch

import requests

from campus_auto_login.adapters.drcom import DrComEportalAdapter
from campus_auto_login.power import AwakeGuard
from campus_auto_login.detector import DetectionEngine
from campus_auto_login.models import Credentials, DetectionResult, PortalPage, Profile


class FakeResponse:
    def __init__(self, text, status_code=200, url="https://www.baidu.com/"):
        self.text = text
        self.status_code = status_code
        self.url = url


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.last_request = None

    def get(self, url, **kwargs):
        self.last_request = (url, kwargs)
        return self.response


class FakeSequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = DetectionEngine()

    def detect_html(self, html, url="http://192.0.2.1/"):
        page = PortalPage(url, url, 200, {}, html)
        return self.engine.detect_from_page(page)

    def test_drcom_eportal_detected(self):
        html = """
        <script>
        var loginUrl = 'http://192.0.2.1:801/eportal/portal/login';
        var callback = 'dr1003';
        var login_method = 1;
        var user_account = '';
        var wlan_user_ip = '';
        var jsVersion = '4.2.1';
        </script>
        """
        outcome = self.detect_html(html)
        self.assertTrue(outcome.supported)
        self.assertEqual(outcome.detected.adapter_id, "drcom_eportal")

    def test_drcom_online_logout_page_detected(self):
        html = """
        <html>
          <head>
            <title>logout</title>
            <!--Dr.COMWebLoginID_1.htm-->
            <script src="a41.js?version=1775617865038"></script>
            <script>
              time='11260 ';flow='145603225 ';oltime=4294967295;
              olflow=4294967295;uid='20260000000';v4ip='192.0.2.10';
              stime='2026-05-06 23:45:02';etime='2026-05-07 23:45:18';
            </script>
          </head>
        </html>
        """
        outcome = self.detect_html(html, "http://192.0.2.1/")
        self.assertTrue(outcome.supported)
        self.assertEqual(outcome.detected.adapter_id, "drcom_eportal")
        self.assertGreaterEqual(outcome.detected.score, 85)
        self.assertEqual(outcome.detected.gateway, "http://192.0.2.1:801")
        self.assertTrue(outcome.detected.login_endpoint.endswith("/eportal/portal/login"))

    def test_srun_detected(self):
        html = """
        <script src="/js/srun_portal.js"></script>
        <script>var ac_id='1'; var n=200; var srun_bx1=true;</script>
        <form action="/cgi-bin/srun_portal"></form>
        """
        outcome = self.detect_html(html, "http://10.0.0.1/")
        self.assertTrue(outcome.supported)
        self.assertEqual(outcome.detected.adapter_id, "srun")

    def test_ruijie_detected(self):
        html = """
        <title>锐捷认证</title>
        <script>var userId=''; var queryString=''; var wlanuserip='';</script>
        <form action="/eportal/InterFace.do?method=login"></form>
        """
        outcome = self.detect_html(html, "http://192.168.0.1/eportal/")
        self.assertTrue(outcome.supported)
        self.assertEqual(outcome.detected.adapter_id, "ruijie_portal")

    def test_h3c_detected(self):
        html = """
        <title>H3C iNode Portal</title>
        <script>var loginLdap=true; var userurl='';</script>
        <form action="/portal/online.do"></form>
        """
        outcome = self.detect_html(html, "http://192.168.1.1/portal/")
        self.assertTrue(outcome.supported)
        self.assertEqual(outcome.detected.adapter_id, "h3c_inode")

    def test_generic_form_detected(self):
        html = """
        <form method="post" action="/login">
          <input name="username" type="text">
          <input name="password" type="password">
        </form>
        """
        outcome = self.detect_html(html, "http://portal.example/login")
        self.assertTrue(outcome.supported)
        self.assertEqual(outcome.detected.adapter_id, "generic_form")

    def test_unknown_page_not_supported(self):
        html = "<html><title>普通网页</title><p>Hello</p></html>"
        outcome = self.detect_html(html, "http://example.com/")
        self.assertFalse(outcome.supported)
        self.assertIsNone(outcome.detected)

    def test_drcom_already_online_login_is_success(self):
        adapter = DrComEportalAdapter()
        detection = DetectionResult(
            supported=True,
            adapter_id="drcom_eportal",
            adapter_name="Dr.COM / ePortal",
            score=100,
            gateway="http://192.0.2.1:801",
            login_endpoint="http://192.0.2.1:801/eportal/portal/login",
            logout_endpoint="http://192.0.2.1:801/eportal/portal/logout",
        )
        response = FakeResponse(
            'dr1003({"result":0,"msg":"IP: 192.0.2.10 已经在线！","ret_code":2});'
        )

        result = adapter.login(
            FakeSession(response),
            detection,
            Credentials("20260000000", "test-password", "@telecom"),
        )

        self.assertTrue(result.success)
        self.assertIn("已在线", result.message)

    def test_check_status_uses_next_url_after_failure(self):
        adapter = DrComEportalAdapter()
        detection = DetectionResult(
            supported=True,
            adapter_id="drcom_eportal",
            adapter_name="Dr.COM / ePortal",
            score=100,
            gateway="http://192.0.2.1:801",
        )
        session = FakeSequenceSession(
            [
                requests.Timeout("first url failed"),
                FakeResponse("ok", 204, "http://www.msftconnecttest.com/connecttest.txt"),
            ]
        )

        self.assertTrue(
            adapter.check_status(
                session,
                detection,
                [
                    "https://www.baidu.com",
                    "http://www.msftconnecttest.com/connecttest.txt",
                ],
            )
        )
        self.assertEqual(len(session.requests), 2)

    def test_check_status_rejects_gateway_redirect(self):
        adapter = DrComEportalAdapter()
        detection = DetectionResult(
            supported=True,
            adapter_id="drcom_eportal",
            adapter_name="Dr.COM / ePortal",
            score=100,
            gateway="http://192.0.2.1:801",
        )
        session = FakeSequenceSession(
            [FakeResponse("<title>portal</title>", 200, "http://192.0.2.1:801/eportal/")]
        )

        self.assertFalse(adapter.check_status(session, detection, ["https://www.baidu.com"]))

    def test_check_status_rejects_captive_marker(self):
        adapter = DrComEportalAdapter()
        detection = DetectionResult(
            supported=True,
            adapter_id="drcom_eportal",
            adapter_name="Dr.COM / ePortal",
            score=100,
            gateway="http://192.0.2.1:801",
        )
        session = FakeSequenceSession(
            [FakeResponse("<script>var user_account='';</script>", 200, "https://www.baidu.com/")]
        )

        self.assertFalse(adapter.check_status(session, detection, ["https://www.baidu.com"]))

    def test_profile_migrates_old_single_check_url(self):
        profile = Profile.from_dict(
            {
                "id": "p1",
                "name": "test",
                "login_url": "http://192.0.2.1/",
                "adapter_id": "drcom_eportal",
                "adapter_name": "Dr.COM / ePortal",
                "gateway": "http://192.0.2.1:801",
                "login_endpoint": "http://192.0.2.1:801/eportal/portal/login",
                "logout_endpoint": "http://192.0.2.1:801/eportal/portal/logout",
                "username": "u",
                "encrypted_password": "p",
                "check_url": "http://example.test/check",
            }
        )

        self.assertEqual(profile.check_url, "http://example.test/check")
        self.assertEqual(profile.check_urls, ["http://example.test/check"])
        self.assertEqual(profile.check_interval_seconds, 30)
        self.assertTrue(profile.resume_reconnect_enabled)

    def test_awake_guard_does_not_crash_without_ctypes(self):
        real_import = __import__

        def blocked_import(name, *args, **kwargs):
            if name == "ctypes":
                raise ImportError("missing _ctypes")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocked_import):
            guard = AwakeGuard()
            self.assertFalse(guard.enable())
            guard.disable()


if __name__ == "__main__":
    unittest.main()
