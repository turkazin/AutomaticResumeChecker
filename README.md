# AutomaticResumeChecker

Программа для сравнения нескольких резюме с описанием вакансии.  
На английском языке.  
На данный момент в основном резюме и описание вакансии только с IT областью.

## Скачать
```bash
git clone https://github.com/turkazin/AutomaticResumeChecker.git
```

## Как запустить
- Версия Python: 3.11.9
- Версия pip: 24.3.1

1. Откройте папку с файлами `AutomaticResumeChecker`.

2. Создайте виртуальное окружение:
   ```bash
   python -m venv venv
   ```

3. Активируйте окружение:
   ```bash
   .\venv\Scripts\activate
   ```

4. После активации окружения, установите необходимые пакеты:
   ```bash
   pip install -r requirements.txt
   ```

5. Установите модель spaCy:
   ```bash
   python -m spacy download en_core_web_lg
   ```

6. Для запуска:
   ```bash
   streamlit run app.py
   ```

После запуска приложения оно перенаправит вас на `localhost` и откроется страница в браузере.

## Тест
Тестовые файлы находятся в папке `testdata`.  
В ней 6 резюме (.docx, .pdf) и описание вакансии (.txt).

1. Возьмите одну из описаний вакансии и вставьте её в форму на странице ("Enter the job description text:").

2. Добавьте 6 резюме ("Browse Files") или перетащите их.

3. Нажмите на кнопку **Analyze**.
