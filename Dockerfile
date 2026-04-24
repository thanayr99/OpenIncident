FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r hf_space/requirements.txt

ENV PORT=7860

EXPOSE 7860

CMD ["python", "hf_space/app.py"]
