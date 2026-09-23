"""Check a translated close and keep its USD and FX evidence together."""

from decimal import Decimal, localcontext
import json

from data_extraction.fx_rates import verify_fx
from fund_pipeline.gbp_reference import COLUMNS, fingerprint, raw_legs
from fund_pipeline.landing import verify_delivery
from fund_pipeline.reconcile import compare_values, read_reference, reconcile
from fund_pipeline.report_gbp import translate


def reconcile_gbp(nav_folder, reference_folder, fx_folder, gbp_folder, business_date, as_of):
    rates = verify_fx(fx_folder)
    if as_of not in rates:
        raise ValueError(f"Missing FX rate for {as_of}")
    manifest = verify_delivery(gbp_folder, as_of, "gbp_references")
    provenance = manifest.get("provenance") or {}
    if (provenance.get("fx_manifest_sha256") != fingerprint(fx_folder)
            or provenance.get("usd_reference_manifest_sha256") != fingerprint(reference_folder)):
        raise ValueError("GBP reference belongs to different FX or USD reference inputs")
    report = reconcile(nav_folder, reference_folder, business_date, as_of, "USD")
    usd = report["close"]
    gbp = translate(usd, rates[as_of])
    expected = read_reference(gbp_folder / "gbp_reference.csv", COLUMNS,
                              ["component"], "amount",
                              {"business_date": as_of, "fund": "NORTHBRIDGE", "currency": "GBP"})
    controls = report["controls"]
    controls += compare_values("gbp_reference", {(field,): gbp[field] for field in ("cash", "nav")},
                               expected, Decimal("0.01"), "GBP", as_of)
    legs = raw_legs(fx_folder, as_of)
    with localcontext() as context:
        context.prec = 40
        reference_rate = legs["GBP"] / legs["USD"]
    controls += compare_values("fx_direction", {("GBP per USD",): Decimal(rates[as_of]["gbp_per_usd"])},
                               {("GBP per USD",): reference_rate}, Decimal("0.0000000000005"),
                               "GBP per USD", as_of)
    fx_manifest = json.loads((fx_folder / "manifest.json").read_text(encoding="utf-8"))
    report.update({"close": gbp, "local_close": usd,
                   "status": "PASS" if all(row["status"] == "PASS" for row in controls) else "FAIL",
                   "gbp_reference_delivery": str(gbp_folder.resolve()),
                   "gbp_reference_manifest_sha256": fingerprint(gbp_folder),
                   "fx_evidence": {"rate": rates[as_of], "delivery": str(fx_folder.resolve()),
                                   "manifest_sha256": fingerprint(fx_folder), "manifest": fx_manifest,
                                   "policy": "Same-date ECB reference; not US-close spot or an executed FX trade"}})
    return report
