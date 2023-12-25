FROM python:3.10-alpine

WORKDIR /app

COPY ./requirements.txt /app/

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

RUN pip install python-dotenv

EXPOSE 5000

COPY . /app/

CMD [ "python3", "congnifuseApi.py" ]
