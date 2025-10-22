import pdfplumber
from docx import Document
import re
from io import BytesIO
from dateutil import parser as date_parser
from datetime import datetime
import spacy
from spacy.pipeline import EntityRuler  
import pandas as pd
import os

# Загрузка lg модели
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    raise OSError("en_core_web_lg not found. Run: python -m spacy download en_core_web_lg")

def load_skills_patterns(csv_path='skills.csv'):
    """Загружает паттерны скиллов из CSV и добавляет в EntityRuler."""
    patterns = []
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            for skill in df['skill'].str.lower().unique():  # Уникальные, lowercase
                patterns.append({"label": "SKILL", "pattern": [{"LOWER": skill}]})
            print(f"Loaded {len(patterns)} skills from {csv_path}")
        except Exception as e:
            print(f"Error loading CSV: {e}. Using fallback.")
    else:
        print(f"{csv_path} not found. Using fallback.")
    
    # Fallback: Минимальный хардкод-лист
    fallback_skills = ['python', 'c++', 'java', 'linux', 'sql']
    for skill in fallback_skills:
        if skill not in [p['pattern'][0]['LOWER'] for p in patterns]:
            patterns.append({"label": "SKILL", "pattern": [{"LOWER": skill}]})
    
    config = {"overwrite_ents": False}
    ruler = nlp.add_pipe("entity_ruler", config=config, before="ner")
    ruler.add_patterns(patterns)
    print(f"Added {len(patterns)} patterns to entity_ruler pipeline")
    return patterns  # Для дебага

# Инициализируем паттерны при загрузке модуля
load_skills_patterns()



def extract_text_from_pdf(pdf_bytes):  # pdf_bytes: bytes
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:  
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Нормализация
    return text

def extract_text_from_docx(docx_bytes):  # docx_bytes: bytes
    doc = Document(BytesIO(docx_bytes))  
    text = "\n".join([para.text for para in doc.paragraphs])
    return text





def extract_resume_data(text):
    doc = nlp(text)  # С lg и динамическими patterns
    
    # Шаг 1: NER PERSON
    person_ents = [ent.text.strip() for ent in doc.ents if ent.label_ == 'PERSON' and len(ent.text.split()) >= 2]
    if person_ents:
        name = person_ents[0]
    else:
        # Шаг 2: Regex for 2-3 capitalized words, lookahead for email/phone
        name_pattern = re.compile(r'\b([A-Z][a-zA-Z\'-]+(?:\s+[A-Z][a-zA-Z\'-]+){1,2})(?=\s*([a-z0-9._%+-]+@|\+?\d|\s*[-––]|\n|$))')
        potential_names = []
        for match in name_pattern.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate.split()) >= 2:
                # Фильтр GPE
                gpe_filter = ['new york', 'san francisco', 'seattle', 'chicago', 'washington', 'los gatos', 'mountain view', 'palo alto', 'almaty', 'kazakhstan', 'russia', 'ca', 'ny', 'wa', 'il', 'dc', 'usa', 'united states', 'berkeley', 'evanston', 'fairfax']
                if not any(city in candidate.lower() for city in gpe_filter):
                    potential_names.append((match.start(), candidate))
        potential_names.sort(key=lambda x: x[0])
        name = potential_names[0][1] if potential_names else "Not found"
    
    # Пост-обработка: Обрезаем email local/domain
    # 1. Удаляем full email
    email_pattern = r'\s*[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'
    name = re.sub(email_pattern, '', name).strip()
    
    # 2. Если local attached (e.g., "Mia Chen mia.chen.devops"), split and remove last if email-like
    parts = name.split()
    if len(parts) > 2 and re.match(r'^[a-z0-9._%+-]+$', parts[-1]):
        name = ' '.join(parts[:-1]).strip()
    
    # 3. If >2 words and contains GPE word, take first 2
    if len(parts) > 2:
        gpe_words = [w for w in parts if any(city in w.lower() for city in gpe_filter)]
        if gpe_words:
            name = ' '.join(parts[:2]).strip()
    
    # Email (separate)
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    email = email_match.group() if email_match else "Not found"
    
    # Phone
    phone_pattern = r'(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{2,4})'
    phone = re.search(phone_pattern, text)
    phone = phone.group() if phone else "Not found"
    
    # Skills 
    skills_text = "Not found"
    skills_match = re.search(r'Skills?\s*(.+?)(?=\s*(Languages?|Certificates?|Projects?|\Z))', text, re.DOTALL | re.IGNORECASE)
    if skills_match:
        bullets = re.findall(r'[•*]\s*(.+?)(?=\n[•*]|\n\n)', skills_match.group(1), re.DOTALL)
        skills_text = '; '.join([b.strip() for b in bullets if b.strip()])
    
    skill_ents = [ent.text.lower() for ent in doc.ents if ent.label_ == 'SKILL']
    if skill_ents:
        skills_text += f" (NER: {' '.join(set(skill_ents))})" if skills_text != "Not found" else ' '.join(set(skill_ents))
    
    # Experience 
    exp_years = 0
    work_match = re.search(r'Work Experience?\s*(.+?)(?=\s*(Skills?|Education|\Z))', text, re.DOTALL | re.IGNORECASE)
    if work_match:
        date_matches = re.findall(r'([A-Za-z]{3})\s+(\d{4})\s*[–-]?\s*([A-Za-z]{3}\s+\d{4}|present)', work_match.group(1))
        for start_month, start_year, end_str in date_matches:
            try:
                start = date_parser.parse(f"{start_month} {start_year}").date()
                if 'present' in end_str:
                    end = datetime.now().date()
                else:
                    end_month, end_year = end_str.split()
                    end = date_parser.parse(f"{end_month} {end_year}").date()
                exp_years += (end - start).days / 365.25
            except:
                pass
    exp_fallback = re.findall(r'(\d+)\s*(years?|yrs?)\s*(of\s+)?experience?', text.lower())
    exp_years += sum(int(y) for y, _, _ in exp_fallback)
    exp_years = round(max(0, exp_years), 1)
    
    # Education 
    education_patterns = ['bachelor', 'master', "bachelor's", "master's", 'phd', 'doctorate']
    found_edu = [pat for pat in education_patterns if pat in text.lower()]
    education = ', '.join(set(found_edu)) if found_edu else "Not found"
    
    return {
        'name': name,
        'email': email,
        'phone': phone,
        'skills': skills_text,
        'experience_years': exp_years,
        'education': education
    }



def extract_vacancy_data(text):
    doc = nlp(text)  # nlp с теми же patterns
    
    position = re.search(r'(Position|Role|Job):\s*(.+)|(.+?)\s*(Engineer|Manager|Developer|Specialist)', text, re.IGNORECASE | re.MULTILINE)
    position = position.group(2) or position.group(3) if position else "Not found"
    
    req_exp = re.findall(r'(\d+)\s*(years?|yrs?)\s*(of\s+)?experience?', text.lower())
    req_exp_years = int(req_exp[0][0]) if req_exp else 0
    
    req_edu_patterns = ["bachelor's", "master's", 'phd']
    req_edu = next((pat for pat in req_edu_patterns if pat in text.lower()), "Not found")
    
    req_skills_text = "Not found"
    skills_match = re.search(r'(Required|Key)\s*Skills?\s*(.+?)(?=\s*Experience|\Z)', text, re.DOTALL | re.IGNORECASE)
    if skills_match:
        req_skills_text = skills_match.group(2).strip()
    else:
        req_skills = [ent.text for ent in doc.ents if ent.label_ in ['SKILL', 'ORG', 'PRODUCT', 'GPE']]
        req_skills_text = ' '.join(set(req_skills)) if req_skills else "Not found"
    
    return {
        'position': position,
        'req_exp_years': req_exp_years,
        'req_education': req_edu,
        'req_skills': req_skills_text
    }