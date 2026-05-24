"""Tests for lat-finder."""

import pytest
from latfinder.core import ScanConfig, SubdomainResult
from latfinder.wordlists import load_wordlist
from latfinder.output import ResultFormatter


def test_load_default_wordlist():
    words = load_wordlist(["default"])
    assert len(words) > 0
    assert all(not w.startswith("#") for w in words)


def test_dedup():
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mktemp(suffix=".txt"))
    tmp.write_text("www\nwww\nmail\n")
    words = load_wordlist([str(tmp)], dedup=True)
    assert words.count("www") == 1
    tmp.unlink()


def test_filter():
    words = load_wordlist(["default"], filter_pattern=r"^mail")
    assert all(w.startswith("mail") for w in words)


def test_multi_wordlist():
    words = load_wordlist(["default", "default"], dedup=False)
    words_dedup = load_wordlist(["default", "default"], dedup=True)
    assert len(words) >= len(words_dedup)


def test_subdomain_result_fqdn():
    r = SubdomainResult(subdomain="www", domain="example.com", ips=["1.2.3.4"])
    assert r.fqdn == "www.example.com"


def test_scan_config_defaults():
    cfg = ScanConfig(target="example.com")
    assert cfg.threads == 50
    assert cfg.adaptive is True
    assert cfg.http_probe is False


def test_formatter_json(capsys):
    import json
    fmt = ResultFormatter("json")
    r = SubdomainResult(subdomain="mail", domain="example.com", ips=["5.6.7.8"],
                        http_status=200, https_status=301)
    fmt.print_result(r)
    data = json.loads(capsys.readouterr().out.strip())
    assert data["fqdn"] == "mail.example.com"
    assert data["http_status"] == 200
