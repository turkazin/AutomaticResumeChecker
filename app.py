import streamlit as st
from extractors import extract_text_from_pdf, extract_text_from_docx, extract_resume_data, extract_vacancy_data
from comparison import calculate_ensemble_score  # Или calculate_match_score, если базовый
import pandas as pd
import mimetypes

# Инициализация session_state
if 'results_df' not in st.session_state:
    st.session_state.results_df = pd.DataFrame()
if 'file_bytes_list' not in st.session_state:
    st.session_state.file_bytes_list = []
if 'vacancy_data' not in st.session_state:
    st.session_state.vacancy_data = None
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False

st.title("Resume Matching with Job Description")

# Загрузка модели spaCy (английская)
try:
    import spacy
    nlp = spacy.load("en_core_web_lg")
except OSError:
    st.error("Install the English spaCy model: python -m spacy download en_core_web_lg")
    st.stop()

# UI
st.header("Job Description")
vacancy_text = st.text_area("Enter the job description text:", height=200, key="vacancy_input")

st.header("Upload Resumes")
uploaded_files = st.file_uploader("Choose PDF or DOCX files", accept_multiple_files=True, type=['pdf', 'docx'], key="files_input")

col1, col2 = st.columns(2)
with col1:
    if st.button("Analyze"):
        if not vacancy_text or not uploaded_files:
            st.warning("Please enter job description and upload at least one resume.")
        else:
            
            vacancy_data = extract_vacancy_data(vacancy_text)
            st.session_state.vacancy_data = vacancy_data
            results = []
            file_bytes_list = []
            for idx, file in enumerate(uploaded_files):
                bytes_data = file.getvalue()
                file_bytes_list.append(bytes_data)
                
                if file.type == "application/pdf":
                    text = extract_text_from_pdf(bytes_data)
                elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    text = extract_text_from_docx(bytes_data)
                else:
                    continue
                
                resume_data = extract_resume_data(text)
                result = calculate_ensemble_score(resume_data, vacancy_data)
                score = result['total_percent']
                
                results.append({
                    'name': resume_data['name'],
                    'match_percent': round(score, 2),
                    'file_name': file.name,
                    'file_index': idx,
                    'breakdown': result['breakdown']  
                })
            
            # Сохраняем сессию в state
            st.session_state.results_df = pd.DataFrame(results).sort_values('match_percent', ascending=False)
            st.session_state.file_bytes_list = file_bytes_list
            st.session_state.analyzed = True

with col2:
    if st.button("Clear Results"):
        st.session_state.results_df = pd.DataFrame()
        st.session_state.file_bytes_list = []
        st.session_state.vacancy_data = None
        st.session_state.analyzed = False
        st.rerun()  # Принудительный rerun для очистки UI

# Вывод результатов
if st.session_state.analyzed and not st.session_state.results_df.empty:
    
    
    st.subheader("Candidate Ranking:")
    st.dataframe(st.session_state.results_df[['name', 'match_percent', 'file_name']], use_container_width=True)
        
    # Скачивания
    st.subheader("Download Resumes")
    for _, row in st.session_state.results_df.iterrows():
        with st.expander(f"{row['name']} - {row['match_percent']}% Match"):
            bytes_data = st.session_state.file_bytes_list[int(row['file_index'])]
            mime_type = mimetypes.guess_type(row['file_name'])[0] or 'application/octet-stream'
            st.download_button(
                label=f"Download {row['file_name']}",
                data=bytes_data,
                file_name=row['file_name'],
                mime=mime_type
            )
else:
    if st.session_state.results_df.empty:
        st.info("Press 'Analyze' to start.")