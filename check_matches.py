#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from fantasy.models import Match

# Check first 10 matches
print("First 10 matches in database:")
for m in Match.objects.order_by('match_number')[:10]:
    print(f"  Match {m.match_number}: {m.home_label} vs {m.away_label} (Group: {m.group})")

# Find Canada match
print("\nSearching for Canada match:")
canada_matches = Match.objects.filter(home_label__icontains='Canada') | Match.objects.filter(away_label__icontains='Canada')
if canada_matches:
    for m in canada_matches:
        print(f"  Match {m.match_number}: {m.home_label} vs {m.away_label}")
else:
    print("  No Canada matches found")
