#!/usr/bin/env python3
"""
Airtable Schema Extractor
Run this script to get the complete schema of your Airtable base.

Usage:
    python scripts/get_airtable_schema.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pyairtable import Api


def get_schema():
    API_KEY = os.getenv("AIRTABLE_PAT")
    BASE_ID = os.getenv("AIRTABLE_BASE_ID")

    if not API_KEY or not BASE_ID:
        print("ERROR: Missing AIRTABLE_PAT or AIRTABLE_BASE_ID in .env")
        return

    api = Api(API_KEY)
    base = api.base(BASE_ID)

    print("=" * 60)
    print("AIRTABLE SCHEMA DEFINITION")
    print(f"Base ID: {BASE_ID}")
    print("=" * 60)

    # Try to get schema from metadata API
    try:
        schema = base.schema()

        for table in schema.tables:
            print(f"\n{'='*60}")
            print(f"TABLE: {table.name}")
            print(f"Table ID: {table.id}")
            print("-" * 60)
            print(f"{'Field Name':<30} {'Type':<20} {'Details'}")
            print("-" * 60)

            for field in table.fields:
                details = ""

                # Get field options/details based on type
                if hasattr(field, 'options') and field.options:
                    opts = field.options

                    # Single/Multiple Select - show choices
                    if hasattr(opts, 'choices') and opts.choices:
                        choices = [c.name for c in opts.choices[:5]]  # First 5
                        if len(opts.choices) > 5:
                            choices.append(f"...+{len(opts.choices)-5} more")
                        details = f"Choices: {choices}"

                    # Linked Record - show linked table
                    elif hasattr(opts, 'linked_table_id'):
                        details = f"Linked to: {opts.linked_table_id}"

                    # Number - show precision
                    elif hasattr(opts, 'precision'):
                        details = f"Precision: {opts.precision}"

                    # Date - show format
                    elif hasattr(opts, 'date_format'):
                        details = f"Format: {getattr(opts, 'date_format', 'default')}"

                print(f"{field.name:<30} {field.type:<20} {details}")

            print()

    except Exception as e:
        print(f"\nMetadata API failed: {e}")
        print("\nFalling back to record-based schema inference...\n")

        # Fallback: infer from records
        tables = ["Contacts", "Matches", "Drafts"]

        for table_name in tables:
            print(f"\n{'='*60}")
            print(f"TABLE: {table_name}")
            print("-" * 60)

            try:
                table = base.table(table_name)
                records = table.all(max_records=10)

                if not records:
                    print("  (Table is empty - cannot infer schema)")
                    continue

                # Collect all fields from multiple records
                all_fields = {}
                for record in records:
                    for field, value in record.get('fields', {}).items():
                        if field not in all_fields:
                            if isinstance(value, list):
                                if value and isinstance(value[0], dict):
                                    all_fields[field] = "List[dict] (Linked Record or Attachment)"
                                else:
                                    all_fields[field] = "List (Multiple Select or Linked Record)"
                            elif isinstance(value, bool):
                                all_fields[field] = "bool (Checkbox)"
                            elif isinstance(value, int):
                                all_fields[field] = "int (Number)"
                            elif isinstance(value, float):
                                all_fields[field] = "float (Number/Currency/Percent)"
                            elif isinstance(value, str):
                                if value.startswith("http"):
                                    all_fields[field] = "str (URL)"
                                elif "@" in value and "." in value:
                                    all_fields[field] = "str (Email)"
                                elif len(value) > 100:
                                    all_fields[field] = "str (Long Text)"
                                else:
                                    all_fields[field] = "str (Single Line Text or Single Select)"
                            else:
                                all_fields[field] = type(value).__name__

                print(f"{'Field Name':<35} {'Inferred Type'}")
                print("-" * 60)
                for field, ftype in sorted(all_fields.items()):
                    print(f"{field:<35} {ftype}")

            except Exception as e:
                print(f"  Error: {e}")

    print("\n" + "=" * 60)
    print("Schema extraction complete!")
    print("=" * 60)


if __name__ == "__main__":
    get_schema()
