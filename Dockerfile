FROM python:3.3.6-alpine

RUN pip install requests
ADD train.py /train.py

ENTRYPOINT ["python", "/train.py"]
