from app.services.duplicate_detector import find_near_duplicates


def test_near_duplicate_detected_via_email_block_and_name_similarity():
    records = [
        {"name": "Suhas Kumar", "email": "suhas@example.com", "phone": "9876543210"},
        {"name": "Suhas Kumarr", "email": "suhas@example.com", "phone": "9876543210"},
        {"name": "Totally Different", "email": "other@example.com", "phone": "1112223333"},
    ]
    matches = find_near_duplicates(records, name_col="name", email_col="email", phone_col="phone")
    assert len(matches) == 1
    assert matches[0].row_indices == (0, 1)
    assert "email" in matches[0].matching_fields


def test_no_false_positive_for_unrelated_records():
    records = [
        {"name": "Alice", "email": "alice@example.com", "phone": "1111111111"},
        {"name": "Bob", "email": "bob@example.com", "phone": "2222222222"},
    ]
    matches = find_near_duplicates(records, name_col="name", email_col="email", phone_col="phone")
    assert matches == []


def test_exact_duplicates_are_not_reported_as_near_duplicates():
    records = [
        {"name": "Alice", "email": "alice@example.com", "phone": "1111111111"},
        {"name": "Alice", "email": "alice@example.com", "phone": "1111111111"},
    ]
    matches = find_near_duplicates(records, name_col="name", email_col="email", phone_col="phone")
    assert matches == []


def test_near_duplicate_never_deleted_only_flagged():
    """Structural guarantee: this module has no delete/merge function at all --
    it can only ever return flagged NearDuplicateMatch records for manual review."""
    import app.services.duplicate_detector as module

    assert not hasattr(module, "remove_duplicates")
    assert not hasattr(module, "merge_records")
