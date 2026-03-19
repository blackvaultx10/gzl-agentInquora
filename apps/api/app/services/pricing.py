from __future__ import annotations

from difflib import SequenceMatcher
from functools import lru_cache

import pandas as pd

from app.config import Settings
from app.models import InquiryItem, InquirySummary


def normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


class PricingEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @lru_cache(maxsize=1)
    def _catalog(self) -> pd.DataFrame:
        frame = pd.read_csv(self.settings.price_catalog_path)
        frame["name_norm"] = frame["name"].map(normalize_token)
        frame["spec_norm"] = frame["specification"].fillna("").map(normalize_token)
        frame["category_norm"] = frame["category"].fillna("").map(normalize_token)
        return frame

    def price_items(self, items: list[InquiryItem]) -> tuple[list[InquiryItem], InquirySummary]:
        priced_items: list[InquiryItem] = []
        flagged_count = 0
        reference_count = 0
        pending_count = 0
        subtotal = 0.0

        for item in items:
            priced_item = item.model_copy(deep=True)
            candidate, score = self._match(item)
            anomalies = list(priced_item.anomalies)

            if candidate is None:
                pending_count += 1
            else:
                reference_count += 1
                priced_item.reference_vendor = str(candidate["vendor"])
                priced_item.reference_unit_price = round(float(candidate["unit_price"]), 2)
                priced_item.reference_total_price = round(priced_item.reference_unit_price * priced_item.quantity, 2)
                priced_item.reference_basis = str(candidate["price_basis"])
                priced_item.reference_match_score = round(score, 3)
                priced_item.price_source = "catalog_reference"

                # Keep legacy fields populated for backward compatibility with saved payloads.
                priced_item.vendor = priced_item.reference_vendor
                priced_item.currency = str(candidate["currency"])
                priced_item.unit_price = priced_item.reference_unit_price
                priced_item.total_price = priced_item.reference_total_price
                priced_item.price_basis = priced_item.reference_basis
                priced_item.match_score = priced_item.reference_match_score
                subtotal += priced_item.reference_total_price

                if score < 0.86:
                    anomalies.append("reference_low_confidence")

            if priced_item.quantity <= 0:
                anomalies.append("invalid_quantity")

            priced_item.anomalies = sorted(set(anomalies))
            if priced_item.anomalies:
                flagged_count += 1
            priced_items.append(priced_item)

        summary = InquirySummary(
            item_count=len(priced_items),
            reference_count=reference_count,
            pending_count=pending_count,
            flagged_count=flagged_count,
            reference_subtotal=round(subtotal, 2),
            currency="CNY",
        )
        return priced_items, summary

    def _match(self, item: InquiryItem) -> tuple[pd.Series | None, float]:
        catalog = self._catalog()
        if catalog.empty:
            return None, 0.0

        name_norm = normalize_token(item.name)
        snippet_norm = normalize_token(item.source_snippet)
        spec_norm = normalize_token(item.specification)
        category_norm = normalize_token(item.category)

        best_score = 0.0
        best_row = None
        for _, row in catalog.iterrows():
            name_score = max(
                SequenceMatcher(None, name_norm, row["name_norm"]).ratio(),
                SequenceMatcher(None, snippet_norm, row["name_norm"]).ratio(),
            )
            spec_score = (
                max(
                    SequenceMatcher(None, spec_norm, row["spec_norm"]).ratio(),
                    SequenceMatcher(None, snippet_norm, row["spec_norm"]).ratio(),
                )
                if spec_norm or row["spec_norm"]
                else 0.4
            )
            category_score = 1.0 if category_norm and category_norm == row["category_norm"] else 0.35
            score = (name_score * 0.55) + (spec_score * 0.3) + (category_score * 0.15)
            if score > best_score:
                best_score = score
                best_row = row

        if best_row is None:
            return None, best_score
        if normalize_token(item.unit) != normalize_token(str(best_row["unit"])):
            return None, best_score
        if best_score < 0.72:
            return None, best_score
        return best_row, best_score
