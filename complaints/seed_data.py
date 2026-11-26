COMPLAINT_CATEGORIES = [
    # code, name, default priority, SLA hours
    ('missed-collection', 'Missed collection', 'high', 48),
    ('overflowing-bin', 'Overflowing bin / container', 'high', 24),
    ('illegal-dumping', 'Illegal dumping', 'medium', 72),
    ('billing', 'Billing or payment dispute', 'medium', 120),
    ('worker-conduct', 'Worker conduct', 'medium', 72),
    ('damaged-bin', 'Damaged or missing bin', 'low', 168),
    ('other', 'Other', 'low', 168),
]


def seed_complaint_categories(ComplaintCategory):
    for i, (code, name, priority, sla) in enumerate(COMPLAINT_CATEGORIES):
        ComplaintCategory.objects.get_or_create(
            code=code,
            defaults={'name': name, 'default_priority': priority, 'sla_hours': sla, 'sort_order': i},
        )
