import os
import joblib
import pdfplumber
import docx
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # 10 MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

MODEL_PATH = "model/model.pkl"
VECT_PATH = "model/vectorizer.pkl"

if not os.path.exists(MODEL_PATH) or not os.path.exists(VECT_PATH):
    raise SystemExit("Run train.py first to generate model files.")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECT_PATH)
feature_names = vectorizer.get_feature_names_out()
coefficients = model.coef_[0]

RED_FLAGS = {
    'Financial': {
        'keywords': ['registration fee', 'security fee', 'processing fee', 'training fee', 'payment', 'deposit', 'transfer', 'rupees', 'rs', 'pay'],
        'reason': 'Financial demand commonly associated with suspicious placement offers.'
    },
    'Urgency': {
        'keywords': ['immediately', 'within 24 hours', 'today only', 'act now', 'limited time', 'immediate joining', 'urgent'],
        'reason': 'Urgency/pressure language used to force quick decisions.'
    },
    'Personal Info': {
        'keywords': ['aadhaar', 'pan card', 'bank account', 'otp', 'password', 'card details', 'sensitive'],
        'reason': 'Request for sensitive personal or financial information.'
    },
    'Unrealistic Claims': {
        'keywords': ['guaranteed job', '100% selection', 'guaranteed salary', 'no interview', 'instant joining', 'direct selection'],
        'reason': 'Unrealistic promises of guaranteed employment.'
    }
}

def extract_text_from_pdf(filepath):
    text = ""
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print("PDF extraction error:", e)
    return text.strip()

def extract_text_from_docx(filepath):
    text = ""
    try:
        doc = docx.Document(filepath)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print("DOCX extraction error:", e)
    return text.strip()

def analyze_text(text):
    if not text.strip():
        return None, "No text found to analyze."

    X = vectorizer.transform([text])
    pred = model.predict(X)[0]
    prob = model.predict_proba(X)[0]
    fake_prob = prob[1]
    
    # Calculate feature contributions for this specific document
    feature_index = X[0].nonzero()[1]
    tfidf_scores = X[0].data
    
    contributions = []
    for idx, score in zip(feature_index, tfidf_scores):
        word = feature_names[idx]
        coef = coefficients[idx]
        contribution = coef * score
        contributions.append((word, contribution, score))
    
    # Sort by contribution to the Fake class (descending)
    contributions.sort(key=lambda x: x[1], reverse=True)
    
    # Take words that have a positive contribution towards being fake
    top_suspicious_words = [item for item in contributions if item[1] > 0][:15]
    
    suspicious_phrases = []
    seen_words = set()
    
    for word, contrib, tfidf in top_suspicious_words:
        flagged = False
        # Check against red flags
        for category, details in RED_FLAGS.items():
            for keyword in details['keywords']:
                if word == keyword or (word in keyword.split() and keyword in text.lower()): 
                    if word not in seen_words:
                        suspicious_phrases.append({
                            'phrase': keyword if keyword in text.lower() else word, 
                            'category': category,
                            'reason': details['reason'],
                            'severity': 'red' if category == 'Financial' or category == 'Personal Info' else 'orange'
                        })
                        seen_words.add(word)
                        flagged = True
                    break
            if flagged:
                break
        
        # If it wasn't caught by predefined red flags but was highly influential to the model
        if not flagged and contrib > 0.4 and word not in seen_words:
            suspicious_phrases.append({
                'phrase': word,
                'category': 'ML Detection',
                'reason': 'This specific phrase strongly correlates with fraudulent patterns in our training data.',
                'severity': 'orange'
            })
            seen_words.add(word)
            
    # Highlight text (Simple highlighting)
    highlighted_text = text
    # Sort phrases by length descending so longer phrases get highlighted first, avoiding partial highlights
    sorted_phrases = sorted(suspicious_phrases, key=lambda x: len(x['phrase']), reverse=True)
    
    for item in sorted_phrases:
        phrase = item['phrase']
        # Escape phrase for regex, but allow word boundaries
        pattern = re.compile(r'\b(' + re.escape(phrase) + r')\b', re.IGNORECASE)
        replacement = f"<mark class='highlight-{item['severity']}'>\\1</mark>"
        highlighted_text = pattern.sub(replacement, highlighted_text)

    # Fallback if regex word boundary missed it
    for item in sorted_phrases:
        if f"highlight-{item['severity']}" not in highlighted_text:
            pattern = re.compile(re.escape(item['phrase']), re.IGNORECASE)
            replacement = f"<mark class='highlight-{item['severity']}'>\g<0></mark>"
            highlighted_text = pattern.sub(replacement, highlighted_text)

    return {
        'fake_prob': fake_prob,
        'genuine_prob': 1.0 - fake_prob,
        'suspicious_phrases': suspicious_phrases,
        'highlighted_text': highlighted_text,
        'char_count': len(text)
    }, None

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        message = ""
        filename = ""
        
        # Check if file was uploaded
        if 'document' in request.files and request.files['document'].filename != '':
            file = request.files['document']
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            ext = filename.lower().split('.')[-1]
            if ext == 'pdf':
                message = extract_text_from_pdf(filepath)
            elif ext in ['doc', 'docx']:
                if ext == 'doc':
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return render_template("index.html", error="Legacy .doc format is unstable in some environments. Please upload as .docx or PDF.")
                message = extract_text_from_docx(filepath)
            else:
                try:
                    os.remove(filepath)
                except:
                    pass
                return render_template("index.html", error="Unsupported file format. Please upload PDF or DOCX.")
                
            try:
                os.remove(filepath)
            except:
                pass
            
            if not message:
                return render_template("index.html", error="Could not extract selectable text from this document. Please upload a text-based PDF or paste the offer letter manually.")
        else:
            message = request.form.get("message", "").strip()

        if not message:
            return render_template("index.html", error="Please upload a document or paste a message.")

        analysis, err = analyze_text(message)
        if err:
            return render_template("index.html", error=err)
            
        fake_pct = analysis['fake_prob'] * 100
        gen_pct = analysis['genuine_prob'] * 100
        
        if fake_pct > 60:
            risk_level = "HIGH RISK"
            prediction = "Potentially Fake Placement"
            color_class = "risk-high"
        elif fake_pct > 30:
            risk_level = "MODERATE RISK"
            prediction = "Suspicious Placement"
            color_class = "risk-medium"
        else:
            risk_level = "LOW RISK"
            prediction = "Appears Low Risk based on text"
            color_class = "risk-low"

        return render_template(
            "results.html",
            risk_level=risk_level,
            prediction=prediction,
            color_class=color_class,
            fake_pct=f"{fake_pct:.1f}",
            gen_pct=f"{gen_pct:.1f}",
            phrases=analysis['suspicious_phrases'],
            highlighted_text=analysis['highlighted_text'],
            filename=filename if filename else "Manual Text Input",
            char_count=analysis['char_count'],
            page_count=1
        )

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
