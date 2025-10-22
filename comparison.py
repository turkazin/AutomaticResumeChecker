from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from extractors import nlp  # Глобальный nlp
import difflib
import re
import string
import pandas as pd
import os
from collections import Counter
from numpy.linalg import norm

# Загрузка CSV скиллов 
skills_df = pd.read_csv('skills.csv')
csv_skills = set(skills_df['skill'].str.lower())


def normalize_text(text):
    """Нормализация: punctuation, lower, multi-word split."""
    translator = str.maketrans('', '', string.punctuation)
    text = text.translate(translator).lower()
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return text

def split_skills(text):
    """Разбивка на список скиллов (пули + слова >3 букв)."""
    bullets = re.findall(r'[•*]\s*(.+?)(?=\n[•*]|\n\n)', text, re.DOTALL | re.IGNORECASE)
    skill_list = [b.strip() for b in bullets if b] or re.findall(r'\b[a-z]{3,}\b', text.lower())
    return skill_list

def simple_bm25_score(skill_list_r, skill_list_v, csv_skills):
    """Simple BM25: boost exact from CSV."""
    r_set = set(skill_list_r)
    v_set = set(skill_list_v)
    intersection = r_set.intersection(v_set)
    csv_boost = sum(1 for s in intersection if s in csv_skills) / max(len(intersection), 1)
    idf_mock = len(intersection) / max(len(r_set.union(v_set)), 1)  # Mock IDF
    return idf_mock * (1 + csv_boost)

def per_skill_similarity(skill_list_r, skill_list_v):
    """Avg similarity по парам скиллов (spaCy vectors)."""
    matches = []
    for sr in skill_list_r:
        for sv in skill_list_v:
            vec_r = nlp(sr).vector
            vec_v = nlp(sv).vector
            norm_vec_r = norm(vec_r)
            norm_vec_v = norm(vec_v)
            sim = vec_r @ vec_v / (norm_vec_r * norm_vec_v) if norm_vec_r > 0 else 0
            if sim > 0.6:
                matches.append(sim)
    return sum(matches) / max(len(matches), 1) if matches else 0

def calculate_ensemble_score(resume_data, vacancy_data):
    skills_r_raw = resume_data['skills']
    skills_v_raw = vacancy_data['req_skills']
    
    # Нормализация и split
    skills_r_norm = normalize_text(skills_r_raw)
    skills_v_norm = normalize_text(skills_v_raw)
    skill_list_r = split_skills(skills_r_raw)
    skill_list_v = split_skills(skills_v_raw)
    
    # 1: TF-IDF (ngram для multi-word)
    vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
    tfidf_vec = vectorizer.fit_transform([skills_r_norm, skills_v_norm])
    tfidf_score = cosine_similarity(tfidf_vec[0:1], tfidf_vec[1:2])[0][0]
    
    # 2: Per-skill embeddings (мощный: avg vectors)
    embeddings_score = per_skill_similarity(skill_list_r, skill_list_v)
    
    # 3: BM25-like (keyword boost from CSV)
    bm25_score = simple_bm25_score(skill_list_r, skill_list_v, csv_skills)
    
    # 4: Fuzzy Jaccard (threshold 0.5 для вариаций)
    words_r = set(re.findall(r'\b[a-z]{3,}\b', skills_r_norm))
    words_v = set(re.findall(r'\b[a-z]{3,}\b', skills_v_norm))
    fuzzy_matches = sum(1 for wr in words_r for wv in words_v if difflib.SequenceMatcher(None, wr, wv).ratio() > 0.5)
    fuzzy_score = fuzzy_matches / max(len(words_r), len(words_v), 1)
    
    # Rules: Edu fuzzy + exp relevance
    edu_terms_r = set(resume_data['education'].lower().split(','))
    edu_terms_v = set(vacancy_data['req_education'].lower().split(','))
    edu_fuzzy = sum(1 for er in edu_terms_r for ev in edu_terms_v if difflib.SequenceMatcher(None, er, ev).ratio() > 0.7) / max(len(edu_terms_r), len(edu_terms_v), 1)
    edu_score = 1.0 if edu_fuzzy > 0.5 else 0.5
    
    exp_base = resume_data['experience_years'] / max(1, vacancy_data['req_exp_years']) if vacancy_data['req_exp_years'] > 0 else 1.0
    exp_bonus = 0.3 if fuzzy_score > 0.5 else 0  # Relevance bonus
    exp_score = min(1.0, exp_base + exp_bonus)
    rules_score = 0.6 * exp_score + 0.4 * edu_score  # Edu вес up
    
    # Ensemble: Embeddings доминирует
    skills_ensemble = 0.2 * tfidf_score + 0.5 * embeddings_score + 0.15 * bm25_score + 0.15 * fuzzy_score
    total_score = skills_ensemble * 0.8 + rules_score * 0.2  # Skills 80%
    
    return {
        'total_percent': round(total_score * 100, 2),  # *100 в конце
        'breakdown': {
            'tfidf': round(tfidf_score * 100, 2),
            'embeddings': round(embeddings_score * 100, 2),
            'bm25': round(bm25_score * 100, 2),
            'fuzzy': round(fuzzy_score * 100, 2),
            'rules': round(rules_score * 100, 2)
        }
    }