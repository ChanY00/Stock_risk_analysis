import json
import logging
from typing import Dict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from analysis.models import MarketIndex
from kis_api.market_index_client import KISMarketIndexClient
from kis_api.market_utils import market_utils


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Fetch KIS market indices (KOSPI/KOSDAQ) via REST once and optionally save into DB. "
        "Diagnostic command to debug credentials, market status, HTTP calls, and DB writes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--index",
            choices=["kospi", "kosdaq", "both"],
            default="both",
            help="Which index to fetch",
        )
        parser.add_argument(
            "--print-only",
            action="store_true",
            help="Do not write to DB; only print fetched payload",
        )
        parser.add_argument(
            "--use-mock",
            action="store_true",
            help="Temporarily enable mock fallback for this run (overrides settings)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Increase logging verbosity for this run",
        )

    def handle(self, *args, **options):
        if options.get("verbose"):
            logging.getLogger().setLevel(logging.INFO)

        # Diagnostics: print effective settings and market status
        self.stdout.write("=== KIS Diagnostics ===")
        self.stdout.write(f"KIS_USE_MOCK: {getattr(settings, 'KIS_USE_MOCK', False)}")
        self.stdout.write(f"KIS_IS_PAPER_TRADING: {getattr(settings, 'KIS_IS_PAPER_TRADING', True)}")
        app_key = getattr(settings, 'KIS_APP_KEY', None)
        app_secret = getattr(settings, 'KIS_APP_SECRET', None)
        self.stdout.write(f"KIS_APP_KEY set: {bool(app_key)} ({(app_key or '')[:6]}...)")
        self.stdout.write(f"KIS_APP_SECRET set: {bool(app_secret)}")

        # Optional one-off mock toggle just for this command
        if options.get("use-mock"):
            setattr(settings, "KIS_USE_MOCK", True)
            self.stdout.write(self.style.WARNING("Temporarily enabling KIS_USE_MOCK=True for this run"))

        # Market status (Seoul time)
        is_open, reason = market_utils.is_market_open()
        self.stdout.write(
            f"Market status: {'OPEN' if is_open else 'CLOSED'} ({reason})"
        )

        # Instantiate a fresh client (reads current settings)
        client = KISMarketIndexClient()

        # Ensure token (prints logs inside)
        token_ok = client._ensure_token()
        self.stdout.write(f"Token ok: {token_ok}")
        if not token_ok and not getattr(settings, 'KIS_USE_MOCK', False):
            self.stdout.write(self.style.ERROR(
                "Failed to obtain token. Set KIS_APP_KEY/SECRET or use --use-mock to fallback."
            ))

        # Fetch
        which = options.get("index", "both")
        payload: Dict[str, Dict] = {}
        if which == "both":
            payload = client.get_all_market_indices() or {}
        else:
            mapping = {
                "kospi": (client.market_indices["KOSPI"]["code"], client.market_indices["KOSPI"]["market_div"]),
                "kosdaq": (client.market_indices["KOSDAQ"]["code"], client.market_indices["KOSDAQ"]["market_div"]),
            }
            code, div = mapping[which]
            data = client.get_market_index_data(code, div)
            if data:
                payload[which] = {
                    "current": data.get("current_value", 0),
                    "change": data.get("change", 0),
                    "change_percent": data.get("change_percent", 0),
                    "volume": data.get("volume", 0),
                    "high": data.get("high", 0),
                    "low": data.get("low", 0),
                    "trade_value": data.get("trade_value", 0),
                }

        # Print payload
        self.stdout.write("\n=== Fetched Payload ===")
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))

        if not payload:
            self.stdout.write(self.style.ERROR(
                "Empty payload. If market is closed and USE_MOCK is False, try --use-mock or run during market hours."
            ))
            return

        if options.get("print-only"):
            self.stdout.write(self.style.SUCCESS("Print-only mode: DB write skipped."))
            return

        # Persist to DB
        saved = 0
        now = timezone.now()
        for name, data in payload.items():
            idx, _ = MarketIndex.objects.get_or_create(
                name=name.upper(),
                defaults={
                    "current_value": 0,
                    "change": 0,
                    "change_percent": 0,
                    "volume": 0,
                },
            )
            idx.current_value = float(data.get("current", 0) or 0)
            idx.change = float(data.get("change", 0) or 0)
            idx.change_percent = float(data.get("change_percent", 0) or 0)
            idx.volume = int(data.get("volume", 0) or 0)
            idx.trade_value = int(data.get("trade_value", 0) or 0)
            idx.high = float(data.get("high", 0) or 0)
            idx.low = float(data.get("low", 0) or 0)
            idx.updated_at = now
            idx.save()
            saved += 1
            self.stdout.write(
                f"Saved {idx.name}: {idx.current_value:,.2f} ({idx.change:+.2f}, {idx.change_percent:+.2f}%)"
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Updated {saved} index rows."))



