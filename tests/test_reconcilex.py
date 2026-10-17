"""Behavioral regression tests for financial correctness and review safety."""

import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from reconcilex.config import Mapping, Settings, load_settings, money_minor, money_text, settings_from_dict
from reconcilex.demo import BANK, CONFIG, EXPECTED, LEDGER
from reconcilex.engine import reconcile
from reconcilex.ingest import load_csv
from reconcilex.models import Dataset, ReconcileError, Transaction
from reconcilex.output import csv_text, render_html, write_report

HEADER = "id,date,amount,currency,reference,description\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def dataset(self, rows, name="input.csv", settings=None, mapping=None):
        path = self.root / name
        path.write_text(HEADER + rows, encoding="utf-8")
        return load_csv(path, mapping, settings)

    def pair(self, left="L,2026-01-01,10.00,SGD,R,Left\n",
             right="B,2026-01-01,10.00,SGD,R,Right\n", config=None):
        settings = settings_from_dict(config or {})
        return reconcile(self.dataset(left, "left.csv", settings),
                         self.dataset(right, "right.csv", settings), settings)

    def demo(self):
        (self.root / "ledger.csv").write_text(LEDGER)
        (self.root / "bank.csv").write_text(BANK)
        s = settings_from_dict(CONFIG)
        return reconcile(load_csv(self.root / "ledger.csv", s.ledger, s),
                         load_csv(self.root / "bank.csv", s.bank, s), s)


class MoneyTests(unittest.TestCase):
    def test_exact_decimal_and_format(self):
        self.assertEqual(money_minor("0.10", 2) + money_minor("0.20", 2), 30)
        self.assertEqual(money_text(-123456, 2), "-1234.56")
        self.assertEqual(money_minor("+10", 2), 1000)

    def test_currency_precision(self):
        self.assertEqual(money_minor("12", 0), 12)
        self.assertEqual(money_text(12, 0), "12")
        self.assertEqual(money_minor("1.234", 3), 1234)
        self.assertEqual(money_text(1, 3), "0.001")

    def test_invalid_money(self):
        for value in ["NaN", "Infinity", "1e3", "1,000.00", "1.001", "1.000", "", " 1", "1.", ".1", "$2", "--2"]:
            with self.subTest(value=value), self.assertRaises(ReconcileError):
                money_minor(value, 2)

    def test_large_values_remain_exact(self):
        self.assertEqual(money_text(money_minor("999999999999999999.99", 2), 2), "999999999999999999.99")
        with self.assertRaises(ReconcileError):
            money_minor("1000000000000000000.00", 2)


class ConfigTests(Fixture):
    def test_defaults_and_explicit_mapping(self):
        s = settings_from_dict({"bank": {"id": "txn", "sign": -1}, "currency_precision": {"CHF": 2}})
        self.assertEqual(s.bank.id, "txn")
        self.assertEqual(s.bank.sign, -1)
        self.assertEqual(s.currency_precision, {"CHF": 2})

    def test_invalid_configurations(self):
        invalid = [{"unknown": 1}, [], {"bank": []}, {"bank": {"surprise": "x"}},
                   {"bank": {"sign": True}}, {"bank": {"sign": 0}},
                   {"bank": {"date": "id"}}, {"bank": {"delimiter": "xx"}},
                   {"bank": {"encoding": "invalid-encoding"}},
                   {"max_rows": 0}, {"max_bytes": True}, {"date_window_days": -1},
                   {"date_window_days": 367}, {"amount_tolerance": 0.1},
                   {"amount_tolerance": "-1"}, {"currency_precision": {}},
                   {"currency_precision": {"usd": 2}}, {"currency_precision": {"USD": True}},
                   {"currency_precision": {"USD": 7}}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ReconcileError):
                settings_from_dict(value)

    def test_config_duplicate_keys_and_malformed_json(self):
        p = self.root / "config.json"
        for text in ['{"max_rows":2,"max_rows":3}', '{"bank":{"id":"x","id":"y"}}', '{bad', 'null']:
            p.write_text(text)
            with self.subTest(text=text), self.assertRaises(ReconcileError):
                load_settings(p)

    def test_missing_config(self):
        with self.assertRaises(ReconcileError):
            load_settings(self.root / "missing.json")


class IngestionTests(Fixture):
    def test_bom_and_hash(self):
        path = self.root / "bom.csv"
        path.write_text(HEADER + "A,2026-01-01,1.00,sgd,,Example\n", encoding="utf-8-sig")
        data = load_csv(path)
        self.assertEqual(data.transactions[0].currency, "SGD")
        self.assertEqual(data.sha256, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_explicit_mapping_encoding_sign_and_date(self):
        path = self.root / "mapped.csv"
        path.write_bytes("Txn;When;Value;CCY;Note\nA;31/01/2026;12.50;SGD;café\n".encode("cp1252"))
        mapping = Mapping(id="Txn", date="When", amount="Value", currency="CCY", description="Note",
                          delimiter=";", date_format="%d/%m/%Y", encoding="cp1252", sign=-1)
        tx = load_csv(path, mapping).transactions[0]
        self.assertEqual((tx.amount_minor, tx.date, tx.description), (-1250, date(2026, 1, 31), "café"))

    def test_optional_columns(self):
        path = self.root / "minimal.csv"
        path.write_text("id,date,amount,currency\nA,2026-01-01,12,SGD\n")
        self.assertEqual(load_csv(path).transactions[0].reference, "")

    def test_bad_headers(self):
        p = self.root / "bad.csv"
        for header in ["", "id,date,amount\n", "id,date,amount,currency,id\n", "id,date,amount,\n"]:
            p.write_text(header)
            with self.subTest(header=header), self.assertRaises(ReconcileError):
                load_csv(p)

    def test_bad_rows_report_row(self):
        invalid = ["A,2026-02-30,1.00,SGD,,x", "A,01/02/2026,1.00,SGD,,x",
                   "A,2026-1-1,1.00,SGD,,x", "A,2026-01-01,NaN,SGD,,x",
                   "A,2026-01-01,1.001,SGD,,x", "A,2026-01-01,1.00,XXX,,x",
                   ",2026-01-01,1.00,SGD,,x", "A,,1.00,SGD,,x",
                   "A,2026-01-01,,SGD,,x", "A,2026-01-01,1.00,,,x",
                   "A,2026-01-01,1.00,SGD", "A,2026-01-01,1.00,SGD,,,extra"]
        for row in invalid:
            with self.subTest(row=row), self.assertRaisesRegex(ReconcileError, "row 2"):
                self.dataset(row + "\n")

    def test_empty_input(self):
        with self.assertRaisesRegex(ReconcileError, "no transactions"):
            self.dataset("")

    def test_duplicate_ids(self):
        with self.assertRaisesRegex(ReconcileError, "duplicate transaction id"):
            self.dataset("A,2026-01-01,1,SGD,,x\nA,2026-01-02,2,SGD,,y\n")

    def test_duplicate_content_retained(self):
        d = self.dataset("A,2026-01-01,1,SGD,R,Same\nB,2026-01-01,1,SGD,r,same\n")
        self.assertEqual(len(d.transactions), 2)
        self.assertTrue(all(t.duplicate_content for t in d.transactions))
        self.assertEqual(len(d.warnings), 2)

    def test_row_and_byte_limits(self):
        row = "A,2026-01-01,1,SGD,,x\n"
        with self.assertRaisesRegex(ReconcileError, "byte input limit"):
            self.dataset(row, settings=replace(Settings(), max_bytes=5))
        with self.assertRaisesRegex(ReconcileError, "data row limit"):
            self.dataset(row + row.replace("A,", "B,"), settings=replace(Settings(), max_rows=1))

    def test_bad_encoding_nul_and_malformed_csv(self):
        path = self.root / "bad.csv"
        for raw in [b'\xff\xfe\x81', (HEADER + 'A,2026-01-01,1,SGD,,"unfinished').encode(),
                    (HEADER + 'A,2026-01-01,1,SGD,,bad\x00text\n').encode()]:
            path.write_bytes(raw)
            with self.subTest(raw=raw[:10]), self.assertRaises(ReconcileError):
                load_csv(path)

    def test_missing_file(self):
        with self.assertRaises(ReconcileError):
            load_csv(self.root / "missing.csv")

    def test_jpy_kwd_custom_precision(self):
        s = settings_from_dict({"currency_precision": {"JPY": 0, "KWD": 3, "CHF": 2}})
        d = self.dataset("A,2026-01-01,12,JPY,,x\nB,2026-01-01,1.234,KWD,,x\nC,2026-01-01,5.50,CHF,,x\n", settings=s)
        self.assertEqual([t.amount_minor for t in d.transactions], [12, 1234, 550])


class MatchingTests(Fixture):
    def test_exact_reference_match(self):
        r = self.pair()
        self.assertEqual(r["summary"]["matched_pairs"], 1)
        self.assertEqual(r["matches"][0]["rule"], "reference_amount_date")

    def test_no_reference_match(self):
        r = self.pair(left="L,2026-01-01,10,SGD,,x\n", right="B,2026-01-01,10,SGD,,y\n")
        self.assertEqual(r["matches"][0]["rule"], "amount_date")

    def test_casefold_reference_but_keep_punctuation(self):
        self.assertEqual(self.pair(right="B,2026-01-01,10,SGD,r,x\n")["summary"]["matched_pairs"], 1)
        self.assertEqual(self.pair(right="B,2026-01-01,10,SGD,R-,x\n")["summary"]["matched_pairs"], 0)

    def test_conflicting_reference_never_matches(self):
        self.assertEqual(self.pair(right="B,2026-01-01,10,SGD,OTHER,x\n")["review_candidates"], [])

    def test_date_boundary(self):
        for day, expected in [(4, 1), (5, 0)]:
            r = self.pair(right=f"B,2026-01-{day:02},10,SGD,R,x\n")
            self.assertEqual(r["summary"]["matched_pairs"], expected)

    def test_date_window_zero(self):
        self.assertEqual(self.pair(right="B,2026-01-02,10,SGD,R,x\n", config={"date_window_days": 0})["matches"], [])

    def test_currency_isolation(self):
        r = self.pair(right="B,2026-01-01,10,USD,R,x\n")
        self.assertEqual(r["matches"], [])
        self.assertEqual(set(r["totals"]), {"SGD", "USD"})
        self.assertEqual(r["totals"]["SGD"]["input_difference"], "10.00")

    def test_negative_values_and_sign(self):
        r = self.pair(left="L,2026-01-01,-10,SGD,R,x\n", right="B,2026-01-01,-10,SGD,R,x\n")
        self.assertEqual(r["summary"]["matched_pairs"], 1)
        self.assertEqual(self.pair(right="B,2026-01-01,-10,SGD,R,x\n", config={"amount_tolerance": "30"})["matches"], [])

    def test_tolerance_is_review_only(self):
        r = self.pair(right="B,2026-01-01,9.98,SGD,R,x\n", config={"amount_tolerance": "0.02"})
        self.assertEqual(r["matches"], [])
        self.assertEqual(r["review_candidates"][0]["difference"], "0.02")
        self.assertIn("amount_difference", r["review_candidates"][0]["reasons"])
        self.assertEqual(self.pair(right="B,2026-01-01,9.97,SGD,R,x\n", config={"amount_tolerance": "0.02"})["review_candidates"], [])

    def test_tolerance_respects_currency_precision(self):
        with self.assertRaisesRegex(ReconcileError, "precision"):
            self.pair(left="L,2026-01-01,10,JPY,R,x\n", right="B,2026-01-01,10,JPY,R,x\n", config={"amount_tolerance": "0.01"})

    def test_ambiguous_candidates_not_greedily_consumed(self):
        left = "L1,2026-01-01,10,SGD,,x\nL2,2026-01-04,10,SGD,,y\n"
        right = "B1,2026-01-01,10,SGD,,a\nB2,2026-01-07,10,SGD,,b\n"
        r = self.pair(left, right)
        self.assertEqual(r["summary"]["matched_pairs"], 0)
        self.assertEqual(r["summary"]["review_candidates"], 3)
        self.assertEqual(r["summary"]["remaining_ledger"], 2)

    def test_exact_candidate_is_not_preferred_over_uncertainty(self):
        r = self.pair(right="B1,2026-01-01,10,SGD,R,x\nB2,2026-01-01,10.01,SGD,R,y\n", config={"amount_tolerance": "0.01"})
        self.assertEqual(r["matches"], [])
        self.assertEqual(len(r["review_candidates"]), 2)

    def test_reference_resolves_equal_amounts_when_both_present(self):
        r = self.pair(left="L1,2026-01-01,10,SGD,R1,x\nL2,2026-01-01,10,SGD,R2,x\n",
                      right="B1,2026-01-01,10,SGD,R1,y\nB2,2026-01-01,10,SGD,R2,y\n")
        self.assertEqual(r["summary"]["matched_pairs"], 2)

    def test_zero_amounts_require_review(self):
        r = self.pair(left="L,2026-01-01,0,SGD,R,x\n", right="B,2026-01-01,0,SGD,R,y\n")
        self.assertEqual(r["matches"], [])
        self.assertIn("zero_amount", r["review_candidates"][0]["reasons"])

    def test_duplicate_content_not_silently_removed(self):
        r = self.pair(left="L1,2026-01-01,10,SGD,R,x\nL2,2026-01-01,10,SGD,R,x\n")
        self.assertEqual(r["matches"], [])
        self.assertEqual(r["summary"]["remaining_ledger"], 2)
        self.assertEqual(len(r["warnings"]["ledger"]), 2)

    def test_candidate_and_comparison_limits(self):
        for config, message in [({"max_candidates": 1}, "edge limit"), ({"max_comparisons": 1}, "comparison limit")]:
            with self.subTest(config=config), self.assertRaisesRegex(ReconcileError, message):
                self.pair(right="B1,2026-01-01,10,SGD,R,x\nB2,2026-01-01,10,SGD,R,y\n", config=config)

    def test_demo_expected_counts_and_control_totals(self):
        r = self.demo()
        self.assertEqual({key:r["summary"][key] for key in EXPECTED}, EXPECTED)
        self.assertEqual(r["totals"]["SGD"]["ledger_total"], "200.50")
        self.assertEqual(r["totals"]["SGD"]["bank_total"], "284.48")
        self.assertEqual(r["totals"]["SGD"]["input_difference"], "-83.98")
        self.assertEqual(r["totals"]["USD"]["input_difference"], "0.00")

    def test_seeded_randomized_oracle_and_invariants(self):
        rng = random.Random(20261017)
        for case in range(150):
            def generate(prefix):
                return tuple(Transaction(f"{prefix}{i}", date(2026,1,1)+timedelta(days=rng.randrange(8)),
                                         rng.choice([-100,0,100,101,200]), rng.choice(["SGD","USD"]),
                                         rng.choice(["", "A", "B"]), "synthetic", i+2)
                             for i in range(rng.randrange(1,10)))
            left, right = generate("L"), generate("B")
            s = settings_from_dict({"amount_tolerance":"0.01"})
            ld, bd = Dataset(left,"l.csv","a"), Dataset(right,"b.csv","b")
            r = reconcile(ld, bd, s)
            oracle = {(l.id,b.id) for l in left for b in right
                      if l.currency == b.currency and abs(l.amount_minor-b.amount_minor)<=1
                      and ((l.amount_minor>0)==(b.amount_minor>0)) and ((l.amount_minor<0)==(b.amount_minor<0))
                      and abs((l.date-b.date).days)<=3
                      and (not l.reference or not b.reference or l.reference.casefold()==b.reference.casefold())}
            actual = {(e["ledger_id"],e["bank_id"]) for e in r["matches"]+r["review_candidates"]}
            self.assertEqual(actual, oracle, case)
            for match in r["matches"]:
                self.assertEqual(sum(lid == match["ledger_id"] for lid, _ in oracle), 1)
                self.assertEqual(sum(bid == match["bank_id"] for _, bid in oracle), 1)
                self.assertEqual(match["ledger_amount"], match["bank_amount"])
                self.assertNotEqual(money_minor(match["ledger_amount"], 2), 0)
            for side, transactions in [("ledger",left),("bank",right)]:
                used=[p[f"{side}_id"] for p in r["matches"]]
                remaining=[p["id"] for p in r[f"remaining_{side}"]]
                self.assertEqual(len(used),len(set(used)))
                self.assertFalse(set(used)&set(remaining))
                self.assertEqual(set(used)|set(remaining),{t.id for t in transactions})
            for code, totals in r["totals"].items():
                self.assertEqual(money_minor(totals["input_difference"],2),
                                 money_minor(totals["matched_difference"],2)+money_minor(totals["remaining_difference"],2))
            permuted=reconcile(replace(ld,transactions=tuple(reversed(left))),replace(bd,transactions=tuple(reversed(right))),s)
            for key in ["matches","review_candidates","remaining_ledger","remaining_bank","totals"]:
                self.assertEqual(r[key],permuted[key],case)


class OutputAndCliTests(Fixture):
    def test_complete_outputs_and_checksums(self):
        result = self.demo()
        out = write_report(result, self.root / "report")
        self.assertEqual(len(list(out.iterdir())),7)
        manifest = json.loads((out/"manifest.json").read_text())
        for filename,digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((out/filename).read_bytes()).hexdigest(),digest)
        self.assertEqual(json.loads((out/"result.json").read_text()),result)
        with (out/"remaining_ledger.csv").open() as f:
            self.assertEqual(len(list(csv.DictReader(f))),5)

    def test_existing_output_preserved(self):
        out=self.root/"existing";out.mkdir();(out/"keep.txt").write_text("unchanged")
        with self.assertRaises(ReconcileError):
            write_report(self.demo(),out)
        self.assertEqual((out/"keep.txt").read_text(),"unchanged")
        self.assertEqual(list(out.iterdir()),[out/"keep.txt"])

    def test_failed_write_cleanup(self):
        out=self.root/"failed"
        with patch("reconcilex.output._csv",side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                write_report(self.demo(),out)
        self.assertFalse(out.exists())

    def test_formula_text_neutralized(self):
        for text in ["=HYPERLINK(\"evil\")", "+cmd", "-cmd", "@SUM(1)", "  =2+2", "\tformula", "\rformula", "\nformula"]:
            with self.subTest(text=text):
                self.assertTrue(csv_text(text).startswith("'"))
        self.assertEqual(csv_text("ordinary"),"ordinary")

    def test_html_escaped_and_json_preserves_text(self):
        r=self.pair(left="=L,2026-01-01,-10,SGD,R,<script>alert(1)</script>\n",
                    right="B,2026-01-10,-10,SGD,R,x\n")
        out=write_report(r,self.root/"safe")
        text=(out/"report.html").read_text()
        self.assertNotIn("<script>",text)
        self.assertIn("&lt;script&gt;",text)
        self.assertIn("default-src 'none'",text)
        with (out/"remaining_ledger.csv").open() as stream:
            row=next(csv.DictReader(stream))
        self.assertEqual(row["id"],"'=L")
        self.assertEqual(row["amount"],"-10.00")
        self.assertEqual(json.loads((out/"result.json").read_text())["remaining_ledger"][0]["id"],"=L")

    def test_cli_demo_and_version(self):
        proc=subprocess.run([sys.executable,"-m","reconcilex","demo","--out",str(self.root/"demo")],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn('"matched_pairs": 3',proc.stdout)
        version=subprocess.run([sys.executable,"-m","reconcilex","--version"],capture_output=True,text=True)
        self.assertEqual(version.returncode,0)
        self.assertIn("1.0.0",version.stdout)

    def test_cli_fail_on_unresolved_and_bad_input(self):
        self.demo()
        config=self.root/"config.json";config.write_text(json.dumps(CONFIG))
        command=[sys.executable,"-m","reconcilex","reconcile",str(self.root/"ledger.csv"),str(self.root/"bank.csv"),"--config",str(config)]
        proc=subprocess.run(command+["--out",str(self.root/"strict"),"--fail-on-unresolved"],capture_output=True,text=True)
        self.assertEqual(proc.returncode,3,proc.stderr)
        self.assertTrue((self.root/"strict"/"report.html").exists())
        (self.root/"ledger.csv").write_text(HEADER)
        bad=subprocess.run(command+["--out",str(self.root/"bad")],capture_output=True,text=True)
        self.assertEqual(bad.returncode,2)
        self.assertNotIn("Traceback",bad.stderr)
        self.assertFalse((self.root/"bad").exists())

    def test_input_files_are_not_modified(self):
        self.demo()
        paths=[self.root/"ledger.csv",self.root/"bank.csv"]
        before=[p.read_bytes() for p in paths]
        subprocess.run([sys.executable,"-m","reconcilex","reconcile",*map(str,paths),"--out",str(self.root/"unchanged")],check=True,capture_output=True)
        self.assertEqual(before,[p.read_bytes() for p in paths])

    def test_html_previews_bounded_but_json_complete(self):
        r=self.demo()
        r["remaining_ledger"]=r["remaining_ledger"]*50
        html=render_html(r)
        self.assertIn("Showing 200 of 250 rows",html)
        self.assertEqual(len(r["remaining_ledger"]),250)


if __name__ == "__main__":
    unittest.main()
