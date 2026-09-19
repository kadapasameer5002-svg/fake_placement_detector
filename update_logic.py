import os

filepath = r"fake_placement_alert\app.py"
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

old_logic = """        # Check against red flags
        for category, details in RED_FLAGS.items():
            for keyword in details['keywords']:
                if word in keyword or keyword in word: 
                    if word not in seen_words:"""

new_logic = """        # Check against red flags
        for category, details in RED_FLAGS.items():
            for keyword in details['keywords']:
                if word == keyword or (word in keyword.split() and keyword in text.lower()): 
                    if word not in seen_words:"""

code = code.replace(old_logic, new_logic)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(code)
print("Logic updated.")
