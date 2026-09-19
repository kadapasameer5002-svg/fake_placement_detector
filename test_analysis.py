import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'fake_placement_alert'))
from fake_placement_alert.app import analyze_text

test1 = "Congratulations! You are selected. Pay ?4,999 registration fee within 24 hours to confirm your job. Send your Aadhaar and bank details immediately."
test2 = "Following your successful interview process, we are pleased to offer you the position of Software Engineer. Your proposed joining date is 5 October 2026. Please complete the standard onboarding documentation through the company's official recruitment channel. No payment is required to accept this offer."

print('=== TEST 1 ===')
res1, err = analyze_text(test1)
print(f"Fake Prob: {res1['fake_prob']*100:.1f}%")
for p in res1['suspicious_phrases']:
    print(f"[{p['category']}] {p['phrase']}: {p['reason']}")

print('\n=== TEST 2 ===')
res2, err = analyze_text(test2)
print(f"Fake Prob: {res2['fake_prob']*100:.1f}%")
for p in res2['suspicious_phrases']:
    print(f"[{p['category']}] {p['phrase']}: {p['reason']}")
