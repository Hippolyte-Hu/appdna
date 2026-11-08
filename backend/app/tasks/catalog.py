"""Public business requirements. Hidden test inputs belong only to the verifier."""

BASE_REQUEST = (
    "We receive support messages about refunds, deliveries, and serious complaints. "
    "Route refunds to Billing, delivery questions to Logistics, and serious complaints "
    "to Customer Care with urgent priority. Leave unrelated messages unassigned."
)
VIP_REQUEST = (
    "VIP customers must receive high priority for ordinary refunds and deliveries. "
    "Keep their destination team unchanged. Serious complaints, including VIP complaints, "
    "must remain urgent. Preserve all existing non-VIP routing."
)


def criteria(scenario: str) -> list[dict]:
    items = [
        {"id": "refund", "requirement": "Refund requests", "team": "Billing", "priority": "default"},
        {"id": "delivery", "requirement": "Delivery questions", "team": "Logistics", "priority": "default"},
        {"id": "complaint", "requirement": "Serious complaints", "team": "Customer Care", "priority": "urgent"},
        {"id": "unrelated", "requirement": "Unrelated questions", "team": None, "priority": "default"},
    ]
    if scenario == "vip":
        items += [
            {"id": "vip_refund", "requirement": "VIP refund requests", "team": "Billing", "priority": "high"},
            {"id": "vip_delivery", "requirement": "VIP delivery questions", "team": "Logistics", "priority": "high"},
            {"id": "vip_complaint", "requirement": "VIP serious complaints", "team": "Customer Care", "priority": "urgent"},
        ]
    return items
